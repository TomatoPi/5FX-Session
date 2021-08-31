#!/usr/bin/env python3

import subprocess as sp
import argparse
import sys

if __name__ == "__main__" :

  parser = argparse.ArgumentParser(description="Jackpatch utility reworked for finer usage")
  parser.add_argument('--save', action='store_true', help='dump current patchbay to stdout')
  parser.add_argument('--load', action='store_true', help='load a patchbay from stdin')
  parser.add_argument('--clear', action='store_true', help='Clear all connections')

  args = parser.parse_args()
  

  if args.save :

    raw = sp.run(["jack_lsp", "-c", "-A"], stdout=sp.PIPE).stdout.decode().split('\n')
    
    ports_by_aliases = dict()
    aliases_by_ports = dict()
    connections = list()

    current_port = None
    status = 0 # 0 : new port   1 : alias   2 : connections
  
    for line in raw :
      if 0 == len(line) :
        continue

      if ' ' == line[0] :
        port = line.split()[0]

        if 0 == status :
          status = 1
          ports_by_aliases[port] = current_port
          aliases_by_ports[current_port] = port

        elif 1 == status :
          connections.append((current_port, port))

      else :
        status = 0
        current_port = line

    print({
      'ports' : list(ports_by_aliases.keys()),
      'graph' : [(aliases_by_ports[src], aliases_by_ports[dest]) for src, dest in connections]
    })
  
  if args.load :

    blob = sys.stdin.readlines()
    
    raw = eval("\n".join(blob)) # Prevent clearing the graph if load failed

  if args.clear :
  
    old = sp.run(["jack_lsp", "-c"], stdout=sp.PIPE).stdout.decode().split('\n')

    current_port = None
  
    for line in old :
      if 0 == len(line) :
        continue

      if ' ' == line[0] :
        port = line.split()[0]
        sp.run(['jack_disconnect', current_port, port])

      else :
        current_port = line

  if args.load :

    for src, dest in raw['graph'] :
      sp.run(['jack_connect', src, dest])
      # TODO add beautifull warning if port doesn't exists
