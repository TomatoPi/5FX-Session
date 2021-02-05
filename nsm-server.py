#!/usr/bin/python3

import subprocess as sp
import os
import time
import liblo
import random
import argparse

class Command :
  def __init__(self, help, call) :
    self.help = help
    self.call = call

class Context :
  def __init__(self, root, port, commands) :

    self.sessionRoot = root
    if not os.path.exists(self.sessionRoot) :
      os.mkdir(self.sessionRoot)

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

  def nsm_add(self, exec) :
    self.server.send(self.address, '/nsm/server/add', ('s', exec))

  def nsm_save(self) :
    self.server.send(self.address, '/nsm/server/save')
  def nsm_open(self, project) :
    self.server.send(self.address, '/nsm/server/open', ('s', project))
  def nsm_new(self, project) :
    self.server.send(self.address, '/nsm/server/new', ('s', project))
  def nsm_duplicate(self, project) :
    self.server.send(self.address, '/nsm/server/duplicate', ('s', project))

  def nsm_close(self) :
    self.server.send(self.address, '/nsm/server/close')
  def nsm_abort(self) :
    self.server.send(self.address, '/nsm/server/abort')
  def nsm_quit(self) :
    self.server.send(self.address, '/nsm/server/quit')
  def nsm_list(self) :
    self.server.send(self.address, '/nsm/server/list')

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

def cmd_add(context) :
  name = input("Program << ")
  context.nsm_add(name)

def cmd_open(context) :
  name = input("Session << ")
  context.nsm_open(name)
def cmd_new(context) :
  name = input("New Session << ")
  context.nsm_new(name)
def cmd_duplicate(context) :
  name = input("New Session << ")
  context.nsm_duplicate(name)

if __name__ == "__main__" :

  parser = argparse.ArgumentParser(
    description='New Session Manager server for 5FX Environment')
  parser.add_argument('root', type=str, nargs='?', help='NSM Session root')
  parser.add_argument('port', type=int, nargs='?', help='NSM Session port')
  args = parser.parse_args()

  if args.root is None :
    args.root = os.environ['HOME'] + '/.5FX/5FX-Session/'
  if args.port is None :
    args.port = random.randint(10000, 32767)
  
  commands = {
    'help' : Command('display command list and help', cmd_help),
    'exit' : Command('quit this program', cmd_quit),
    'add' : Command('add a programm to the session', cmd_add),
    'save' : Command('save current session', Context.nsm_save),
    'open' : Command('open a session', cmd_open),
    'new' : Command('create a new session', cmd_new),
    'duplicate' : Command('duplicate current session', cmd_duplicate),
    'close' : Command('save current session', Context.nsm_close),
    'abort' : Command('save current session', Context.nsm_abort),
    'quit' : Command('save current session', Context.nsm_quit),
    'list' : Command('save current session', Context.nsm_list),
    }
  context = Context(args.root, args.port, commands)

  while context.isRunning :

    cmd = input("SessionFX << ")

    if 0 < len(cmd) :
      if cmd in commands :
        commands[cmd].call(context)

  context.nsm_quit()
  context.server.stop()
  context.daemon.terminate()