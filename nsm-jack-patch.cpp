#include <5FX/jackwrap.hpp>

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

std::atomic_flag run;

std::unique_ptr<lo::ServerThread> osc_server;
std::unique_ptr<lo::Address> nsm_server;
std::string nsm_url;
std::atomic_flag nsm_client_opened;
bool has_nsm;

struct Config
{
  std::unordered_set<std::string> patchbays;
  std::string current_patch;
} config;

struct Session
{
  std::string instance_path;
  std::string display_name;
  std::string client_id;
} session;

struct FileOpenFailure { std::string path; };
struct DirectoryCreationFailure { std::string path; };
struct SoundFontLoadingFailure { std::string path; };

struct HomeNotFound {};
struct OSCServerOpenFailure {};

std::optional<std::string> get_env(const std::string& var, char const* env[])
{
  std::regex regex(var + "=(.*)");
  std::cmatch match;
  for (int i = 0; env && env[i]; ++i) {
    if (std::regex_match(env[i], match, regex)) {
      return std::make_optional(match[1]);
    }
  }
  return std::nullopt;
}

void clear_patch()
{
  system(std::string("jack-patch.py --clear").c_str());
}
void save_patch(const std::string& path)
{
  system((std::string("jack-patch.py --save > ") + path).c_str());
}
void load_patch(const std::string& path)
{
  if (!std::filesystem::exists(path))
  {
    clear_patch();
    save_patch(path);
  }
  system((std::string("jack-patch.py --load < ") + path).c_str());
}

Config default_config(const std::string& home)
{
  Config config;
  config.current_patch = home + "/patchbays/default.pbay";
  config.patchbays = { config.current_patch };
  return config;
}
Config load_config_file(const std::string& rootpath)
{
  Config config;
  const std::filesystem::path root = rootpath;
  {
    const std::filesystem::path path(root / "patchbays");
    for(auto const& dir_entry: std::filesystem::directory_iterator{path})
      config.patchbays.emplace(dir_entry.path());
  }{
    const std::filesystem::path path(root / "config.cfg");
    std::ifstream file(path);
    if (file.fail()) {
      throw FileOpenFailure{ path };
    }
    file >> config.current_patch;
    file.close();
  }
  return config;
}
void save_config(const Config& config, const std::string& rootpath)
{
  const std::filesystem::path root(rootpath);

  if (!std::filesystem::exists(root / "patchbays")) {
    if (!std::filesystem::create_directories(root / "patchbays")) {
      throw DirectoryCreationFailure{ root / "patchbays "};
    }
  }
  std::string path(root / "config.cfg");
  std::ofstream file(path);
  if (file.fail()) {
    throw FileOpenFailure{ path };
  }
  file << config.current_patch;
  file.close();
}

void sigkill(int)
{
  run.clear();
}

int main(int argc, char const* argv[], char const* env[])
{

  std::srand(std::time(nullptr));

  auto home = get_env("HOME", env);
  if (!home.has_value()) {
    throw HomeNotFound{};
  }

  auto nsm = get_env("NSM_URL", env);
  has_nsm = nsm.has_value();
  if (nsm.has_value()) {

    /* Create connection to NSM server */

    nsm_url = nsm.value();
    nsm_server = std::make_unique<lo::Address>(nsm_url);
    std::cout << "Start under NSM session at : " << nsm_url << std::endl;
    bool success(false);
    for (int i = 0; i < 5; ++i) {
      osc_server = std::make_unique<lo::ServerThread>(8000 + (std::rand() % 1000));
      if (osc_server->is_valid()) {
        success = true;
        break;
      }
    }
    if (!success) {
      throw OSCServerOpenFailure{};
    }

    osc_server->add_method("/nsm/client/open", "sss",
      [](lo_arg** argv, int) -> void
      {
        session.instance_path = &argv[0]->s;
        session.display_name = &argv[1]->s;
        session.client_id = &argv[2]->s;
        nsm_client_opened.clear();
      });
    osc_server->add_method("/nsm/client/save", "",
      [](lo_arg** argv, int) -> void
      {
        const std::filesystem::path path = session.instance_path;
        const std::filesystem::path patch = path / "patchbays" / config.current_patch;
        save_patch(patch);
        save_config(config, path);
        nsm_server->send("/reply", "ss", "/nsm/client/save", "OK");
      });
    
    osc_server->add_method("/patcher/new", "s",
      [](lo_arg** argv, int) -> void
      {
        const std::filesystem::path path = session.instance_path;
        const std::filesystem::path oldpatch = path / "patchbays" / config.current_patch;
        const std::filesystem::path newpatch = path / "patchbays" / &argv[0]->s;
        save_patch(oldpatch);
        clear_patch();
        save_patch(newpatch);
        config.current_patch = &argv[0]->s;
        config.patchbays.emplace(config.current_patch);
      });
    osc_server->add_method("/nsm/client/save", "",
      [](lo_arg** argv, int) -> void
      {
        const std::filesystem::path path = session.instance_path;
        const std::filesystem::path patch = path / "patchbays" / config.current_patch;
        save_patch(patch);
      });
    osc_server->add_method("/nsm/client/load", "s",
      [](lo_arg** argv, int) -> void
      {
        const std::filesystem::path path = session.instance_path;
        const std::filesystem::path oldpatch = path / "patchbays" / config.current_patch;
        const std::filesystem::path newpatch = path / "patchbays" / &argv[0]->s;
        save_patch(oldpatch);
        clear_patch();
        save_patch(newpatch);
        config.current_patch = &argv[0]->s;
        config.patchbays.emplace(config.current_patch);
      });
    osc_server->add_method("/nsm/client/clear", "",
      [](lo_arg** argv, int) -> void
      {
        clear_patch();
      });
    
    
    osc_server->start();

    /* Announce client and wait for response */
    nsm_client_opened.test_and_set();
    nsm_server->send(
      "/nsm/server/announce", "sssiii",
      "5FX-Patcher", "::", argv[0], 1, 1, getpid());
    while (nsm_client_opened.test_and_set()) {
      std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    const std::filesystem::path path = session.instance_path;

    if (std::filesystem::exists(path)) {
      config = load_config_file(path);
    } else {
      config = default_config(path);
      save_config(config, path);
    }
    const std::filesystem::path patch = path / "patchbays" / config.current_patch;
    clear_patch();
    load_patch(patch);

  } else {
    std::cout << "Start in Standalone mode" << std::endl;

    session.instance_path = home.value() + "/.5FX/5FX-Patcher/";
    session.client_id = "5FX-Patcher";
    session.display_name = "5FX-Patcher";

    config = default_config(home.value());
  }

  /* load session and everything else */

  if (has_nsm) {
    nsm_server->send("/reply", "ss", "/nsm/client/open", "OK");
  } else {
    std::cout << "Ready" << std::endl;
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
      if (!nsm_client_opened.test_and_set())
      {
        const std::filesystem::path path = session.instance_path;

        if (std::filesystem::exists(path)) {
          config = load_config_file(path);
        } else {
          config = default_config(path);
          save_config(config, path);
        }
        const std::filesystem::path patch = path / "patchbays" / config.current_patch;
        clear_patch();
        load_patch(patch);
      }
    }
  } while (run.test_and_set());

  osc_server->stop();

  return 0;
}
