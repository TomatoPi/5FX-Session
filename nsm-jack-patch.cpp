#include <5FX/sfx.hpp>
#include <5FX/nsmwrap.hpp>
#include <5FX/logger.hpp>

#include <sys/types.h>
#include <unistd.h>

#include <lo/lo_cpp.h>

#include <unordered_set>
#include <filesystem>
#include <iostream>
#include <optional>
#include <fstream>
#include <memory>
#include <string>
#include <atomic>
#include <thread>
#include <chrono>
#include <regex>
#include <set>

#include <signal.h>

constexpr const char* EmptyPatch = "{'ports': [], 'graph': []}";

MAKE_DEFAULTED(CurrentPatch, std::string, "default.pb");

sfx::Logger logger;

struct Config : public sfx::Introspectable<CurrentPatch>
{
  sfx::nsm::Config* session = nullptr;

  std::filesystem::path session_path() const
  {
    return session->get<sfx::nsm::InstancePath>().get();
  }
  std::filesystem::path patchbays_path() const
  {
    return session_path() / "patchbays";
  }
  std::filesystem::path patch_path() const
  {
    return patchbays_path() / get<CurrentPatch>().get();
  }
  std::filesystem::path config_path() const
  {
    return session_path() / "config.cfg";
  }

  void save() const
  {
    sfx::FileGuard config_file{ config_path(), *this };
    sfx::sofstream stream{ config_file };
    stream.get() << *this;
    logger << "Save Global Config" << std::endl;
  }
};

std::atomic_flag run;

std::shared_ptr<sfx::nsm::Session> nsm_session;
sfx::nsm::Config default_config;
bool has_nsm;

Config global_config;

namespace details
{
  void clear_patch()
  {
    system(std::string("jack-patch.py --clear").c_str());
  }
  void save_patch(const std::string& path)
  {
    sfx::FileGuard(path, EmptyPatch);
    system((std::string("jack-patch.py --save > ") + path).c_str());
  }
  void load_patch(const std::string& path)
  {
    sfx::FileGuard(path, EmptyPatch, std::make_optional([](const auto& path){
      clear_patch();
      save_patch(path);
    }));
    system((std::string("jack-patch.py --load < ") + path).c_str());
  }
}

void switch_patch(const std::string& path)
{
  const auto oldpatch = global_config.patch_path();
  const auto newpatch = global_config.patchbays_path() / path;
  details::save_patch(oldpatch);
  details::clear_patch();
  details::save_patch(newpatch);
  global_config.get<CurrentPatch>().set(newpatch);
}


void sigkill(int)
{
  run.clear();
}

int main(int argc, char const* argv[], char const* env[])
{

  std::srand(std::time(nullptr));

  auto nsm_status = sfx::nsm::try_connect_to_server(argv[0], "5FX-Patcher", [](const sfx::nsm::Session& session){
    sfx::FileGuard patch_file{ global_config.patch_path(), global_config };
    details::save_patch(patch_file);
    global_config.save();
    return true;
  });

  if (0 == nsm_status.index())
  {
    default_config = std::get<sfx::nsm::Config>(nsm_status);
    global_config.session = &default_config;
    logger << "NSM not found... standalone mode :\n" << default_config << std::endl;
    has_nsm = false;
    global_config.save();
  }
  else if (1 ==  nsm_status.index())
  {
    nsm_session = std::get<std::shared_ptr<sfx::nsm::Session>>(nsm_status);
    global_config.session = &nsm_session->config;
    logger.open(global_config.session_path() / "lastest.log");

    logger << "NSM found : " << nsm_session->nsm_server->hostname() << ":" << nsm_session->nsm_server->port() << std::endl;
    logger << "Config : " << nsm_session->config << std::endl;
    has_nsm = true;
    
    nsm_session->add_method("/patcher/new", "s", "patchbay", 
      [](lo_arg** argv, int) -> void
      {
        switch_patch(&argv[0]->s);
        logger << "New : " << &argv[0]->s << std::endl;
      });
    nsm_session->add_method("/patcher/save", "", "", 
      [](lo_arg** argv, int) -> void
      {
        details::save_patch(global_config.patch_path());
        logger << "Save to : " << global_config.patch_path() << std::endl;
      });
    nsm_session->add_method("/patcher/load", "s", "patchbay", 
      [](lo_arg** argv, int) -> void
      {
        switch_patch(&argv[0]->s);
        logger << "Loads from : " << &argv[0]->s << std::endl;
      });
    nsm_session->add_method("/patcher/clear", "", "",
      [](lo_arg** argv, int) -> void
      {
        details::clear_patch();
        logger << "Clear" << std::endl;
      });
  }

  /* load session and everything else */

  if (has_nsm) {
    nsm_session->nsm_server->send("/reply", "ss", "/nsm/client/open", "OK");
  } else {
    logger << "Ready" << std::endl;
  }

  signal(SIGTERM, sigkill);

  run.test_and_set();
  do {
    if (!has_nsm) {
      std::string input;
      std::cin >> input;
      if (input != std::string("quit")) {
        run.clear();
      }
    } else {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
  } while (run.test_and_set());

  nsm_session->osc_server->stop();

  return 0;
}
