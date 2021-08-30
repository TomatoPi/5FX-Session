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

    for key, value in kwargs.items() :
      self.__dict__[key] = value

  def call(self, cmd, context) :
    msg = liblo.Message(f"/nsm/server/{cmd}")
    for t, arg in self.args :
      val = input(f"{arg} << ")
      if "project" == arg :
        context.currentSession = val
      msg.add((t, val))
    # inj = f"""context.server.send(context.address, { ', '.join(['"/nsm/server/' + cmd + '"'] + ['("' + t + '", input("' + arg + '" + " : "))' for t, arg in self.args]) })"""
    # print(inj)
    # eval(inj)
    context.server.send(context.address, msg)
    if self.quit :
      context.currentSession = None

class Command :
  def __init__(self, help, routine) :
    self.help = help
    self.routine = routine

  def call(self, cmd, context) :
    self.routine(context)

class Context :
  def __init__(self, root, port, commands) :

    self.currentSession = None

    self.sessionRoot = root
    if not os.path.exists(self.sessionRoot) :
      os.makedirs(self.sessionRoot)

    self.commands = commands
    self.isRunning = True
    self.daemon = sp.Popen(["nsmd", "--session-root", self.sessionRoot, "--osc-port", str(port)])
    self.url = 'osc.udp://localhost:' + str(port)
    self.address = liblo.Address(self.url)

    os.environ['NSM_URL'] = self.url

    success = False
    for t in range(5) :
      try :
        self.server = liblo.ServerThread(port + random.randint(1, 10000), liblo.UDP)
        success = True
      except liblo.ServerError :
        pass
    if not success :
      exit(-1)
          

    self.server.add_method('/reply', None, nsm_reply_callback, self)
    self.server.start()

def nsm_reply_callback(path, args, types, address, context) :
  replypath = args[0]
  messagepath = args[1]

  if 0 == len(messagepath) :
    return
  
  print(replypath, messagepath)

def cmd_help(context) :
  commands = context.commands
  for cmd in commands :
    print(cmd, ':', commands[cmd].help)

def cmd_quit(context) :
  context.isRunning = False

def cmd_show(context) :
  print(f"""
  Context : Session = "{ context.currentSession }"
  Clients :
  {
    sp.run(["cat", os.path.join(context.sessionRoot, context.currentSession, "session.nsm")], stdout = sp.PIPE) if context.currentSession is not None else ""
  }
  """)

if __name__ == "__main__" :

  parser = argparse.ArgumentParser(
    description='New Session Manager server for 5FX Environment')
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
    'open' : NSMCommand('Saves the current session and loads a new session.', ('s', "project")),
    'new' : NSMCommand('Saves the current session and creates a new session.', ('s', "project")),
    'duplicate' : NSMCommand('Saves and closes the current session, makes a copy, and opens it.', ('s', "project")),

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