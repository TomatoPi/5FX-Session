#!/usr/bin/python3

import subprocess as sp
import os
import time
import liblo
import random
import argparse

class NSMCommand :
  def __init__(self, help, *args, **kwargs) :
    self.help = help
    self.args = args

    self.quit = False
    self.load = False

    for key, value in kwargs.items() :
      self.__dict__[key] = value

  def call(self, cmd, context, **kwargs) :
    msg = liblo.Message(f"/nsm/server/{cmd}")
    for t, arg in self.args :

      if arg in kwargs :
        val = kwargs[arg]
      else :
        val = input(f"{arg} << ")

      if self.load :
        context.currentSession = val

      msg.add((t, val))

    context.nsm_server.server.send(context.address, msg)
    if self.quit :
      context.currentSession = ""

class Command :
  def __init__(self, help, routine) :
    self.help = help
    self.routine = routine

  def call(self, cmd, context, **kwargs) :
    self.routine(context)

class Server :
  def __init__(self, port) -> None:

    success = False
    for t in range(5) :
      try :
        self.port = port + random.randint(1, 10000)
        self.url = 'osc.udp://localhost:' + str(self.port)
        self.server = liblo.ServerThread(self.port, liblo.UDP)
        success = True
      except liblo.ServerError :
        pass
    if not success :
      exit(-1)

class Context :
  def __init__(self, root, port, commands) :

    self.currentSession = ""

    self.sessionRoot = root
    if not os.path.exists(self.sessionRoot) :
      os.makedirs(self.sessionRoot)

    self.nsm_server = Server(port+1)
    self.sfx_server = Server(port+2)

    self.url = 'osc.udp://localhost:' + str(port)
    self.address = liblo.Address(self.url)

    os.environ['NSM_URL'] = self.url
    os.environ['SFX_URL'] = self.sfx_server.url

    self.commands = commands
    self.isRunning = True
    self.daemon = sp.Popen(["nsmd", "--session-root", self.sessionRoot, "--osc-port", str(port)], env=os.environ)

    self.nsm_server.server.add_method('/reply', None, nsm_reply_callback, self)
    self.nsm_server.server.start()

    self.sfx_server.server.add_method('/sfx/new/client', None, sfx_new_client_callback, self)
    self.sfx_server.server.add_method('/sfx/new/method', None, sfx_new_method_callback, self)
    self.sfx_server.server.start()
    

    print('NSM_URL =', os.environ['NSM_URL'])
    print('SFX_URL =', os.environ['SFX_URL'])

  def call(self, cmd, **kwargs) :
    self.commands[cmd].call(cmd, self, **kwargs)
    
  def reload(self) :
    tmp = self.currentSession
    self.call('abort')
    time.sleep(5)
    self.call('open', project = tmp)


def nsm_reply_callback(path, args, types, address, context) :
  replypath = args[0]
  messagepath = args[1]

  if 0 == len(messagepath) :
    return
  
  print("5FX-Server Recieved : ", replypath, messagepath)



def sfx_new_client_callback(path, args, types, address, context) :
  client_id = args[0]
  client_port = args[1]
  
  print("5FX-Server New Client : ", client_id, client_port)


def sfx_new_method_callback(path, args, types, address, context) :

  client_id = args[0]
  method = args[1]
  params = args[2]
  description = args[3]
  
  print("5FX-Server New Method : ", client_id, method, params, description)


def cmd_help(context) :
  commands = context.commands
  for cmd in commands :
    print(cmd, ':', commands[cmd].help)

def cmd_quit(context) :
  context.isRunning = False

def cmd_add(context) :
  name = input("Program << ")
  context.nsm_add(name)

def cmd_reload(context) :
  context.reload()
def cmd_show(context) :
  if "" != context.currentSession :
    print(f"""
Context :
  Session = "{ context.currentSession }"

Clients :

{
sp.run(["cat", os.path.join(context.sessionRoot, context.currentSession, "session.nsm")], stdout = sp.PIPE).stdout.decode()
}
""")
  else :
    print("No Session oppend...")

if __name__ == "__main__" :

  parser = argparse.ArgumentParser(
    description='Non Session Manager server for 5FX Environment')
  parser.add_argument('--root', type=str, nargs='?', help='NSM Session root')
  parser.add_argument('--port', type=int, nargs='?', help='NSM Session port')
  parser.add_argument('--session', type=str, nargs='?', help='NSM Session to load')
  parser.add_argument('--no-cli', action='store_true', help='Start without command line interface')
  args = parser.parse_args()

  if args.root is None :
    args.root = os.environ['HOME'] + '/.5FX/5FX-Session/'
  if args.port is None :
    args.port = random.randint(10000, 32767)
  
  commands = {
    'help' : Command('display command list and help', cmd_help),
    'exit' : Command('quit this program', cmd_quit),

    'show' : Command('Print current session', cmd_show),

    'add' : NSMCommand('Adds a client to the current session.', ('s', "client")),
    'save' : NSMCommand('Saves the current session.'),
    'open' : NSMCommand('Saves the current session and loads a new session.', ('s', "project"), load=True),
    'new' : NSMCommand('Saves the current session and creates a new session.', ('s', "project"), load=True),
    'duplicate' : NSMCommand('Saves and closes the current session, makes a copy, and opens it.', ('s', "project"), load=True),
    'reload' : Command('Abort session and reopen it', cmd_reload),

    'close' : NSMCommand('Saves and closes the current session.', quit=True),
    'abort' : NSMCommand('Closes the current session WITHOUT SAVING', quit=True),
    'quit' : NSMCommand('Saves and closes the current session and terminates the server.', quit=True),

    'list' : NSMCommand('Lists available projects. One /reply message will be sent for each existing project.'),
    }
  context = Context(args.root, args.port, commands)

  if not args.session is None :
    time.sleep(5)
    context.nsm_open(args.session)

  while context.isRunning :

    if args.no_cli :
      time.sleep(1)

    else :
      cmd = input("SessionFX << ")

      if 0 < len(cmd) :
        if cmd in commands :
          commands[cmd].call(cmd, context)

  context.nsm_quit()
  context.server.stop()
  context.daemon.terminate()