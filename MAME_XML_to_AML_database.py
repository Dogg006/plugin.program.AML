#!/usr/bin/python
# -*- coding: utf-8 -*-
# Converts MAME output XML into AML database
#

# Copyright (c) 2016 Wintermute0110 <wintermute0110@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# --- INSTRUCTIONS -------------------------------------------------------------
#
# ------------------------------------------------------------------------------

# --- Python standard library ---
import xml.etree.ElementTree as ET 
import re
import sys
import json
import io

# --- "Constants" -------------------------------------------------------------
MAME_XML_filename               = 'MAME.xml'
Main_DB_filename                = 'MAME_info.json'
Machines_DB_filename            = 'idx_Machines.json'
Machines_NoCoin_DB_filename     = 'idx_Machines_NoCoin.json'
Machines_Mechanical_DB_filename = 'idx_Machines_Mechanical.json'
NUM_MACHINES = 50000

# -------------------------------------------------------------------------------------------------
# Utility functions
# -------------------------------------------------------------------------------------------------
def fs_write_JSON(json_filename, json_data):
    # >> Write JSON data
    try:
        with io.open(json_filename, 'wt', encoding='utf-8') as file:
          file.write(unicode(json.dumps(json_data, ensure_ascii = False, sort_keys = True, indent = 2, separators = (',', ': '))))
    except OSError:
        # gui_kodi_notify('Advanced Emulator Launcher - Error', 'Cannot write {0} file (OSError)'.format(roms_json_file))
        pass
    except IOError:
        # gui_kodi_notify('Advanced Emulator Launcher - Error', 'Cannot write {0} file (IOError)'.format(roms_json_file))
        pass

# -----------------------------------------------------------------------------
# Incremental Parsing approach B (from [1])
# -----------------------------------------------------------------------------
# Do not load whole MAME XML into memory! Use an iterative parser to
# grab only the information we want and discard the rest.
# See http://effbot.org/zone/element-iterparse.htm [1]
#
context = ET.iterparse(MAME_XML_filename, events=("start", "end"))
context = iter(context)
event, root = context.next()
mame_version_str = 'MAME ' + root.attrib['build']
print('MAME version is "{0}"'.format(mame_version_str))

# --- Data variables ---
# Create a dictionary of the form,
#   machines = { 'machine_name' : machine, ...}
#
def fs_new_machine():
    m = {'sourcefile'    : u'',
         'isbios'        : False,
         'isdevice'      : False,
         'ismechanical'  : False,
         'runnable'      : False,
         'cloneof'       : u'',
         'romof'         : u'',
         'sampleof'      : u'',
         'description'   : u'', 
         'year'          : u'', 
         'manufacturer'  : u'',
         'haveCoin'      : False,
         'coins'         : 0,
         'driver_status' : u''
    }

    return m

machines = {}
machine_name = ''
num_iteration = 0
num_machines = 0
print('Reading MAME XML file ...')
for event, elem in context:
    # --- Debug the elements we are iterating from the XML file ---
    # print('Event     {0:6s} | Elem.tag    "{1}"'.format(event, elem.tag))
    # print('                   Elem.text   "{0}"'.format(elem.text))
    # print('                   Elem.attrib "{0}"'.format(elem.attrib))

    # <machine> tag start event includes <machine> attributes
    if event == 'start' and elem.tag == 'machine':
        machine = fs_new_machine()
        
        # --- Process <machine> attributes ---
        # #REQUIRED attribute
        if 'name' not in elem.attrib:
            print('"name" attribute not found in <machine> tag. Aborting.')
            sys.exit(10)
        else:
            machine_name = elem.attrib['name']
        # #IMPLIED attribute
        if 'sourcefile' not in elem.attrib:
            print('"sourcefile" attribute not found in <machine> tag. Aborting.')
            sys.exit(10)
        else:
            machine['sourcefile'] = elem.attrib['sourcefile']
        # Optional, default no
        if 'isbios' not in elem.attrib: machine['isbios'] = False
        else:                           machine['isbios'] = True if elem.attrib['isbios'] == u'yes' else False
        if 'isdevice' not in elem.attrib: machine['isdevice'] = False
        else:                             machine['isdevice'] = True if elem.attrib['isdevice'] == u'yes' else False
        if 'ismechanical' not in elem.attrib: machine['ismechanical'] = False
        else:                                 machine['ismechanical'] = True if elem.attrib['ismechanical'] == u'yes' else False
        # Optional, default yes
        if 'runnable' not in elem.attrib: machine['runnable'] = True
        else:                             machine['runnable'] = False if elem.attrib['runnable'] == u'no' else True

        # #IMPLIED attribute
        if 'cloneof' in elem.attrib:
            machine['cloneof'] = elem.attrib['cloneof']

        # #IMPLIED attribute
        if 'romof' in elem.attrib:
            machine['romof'] = elem.attrib['romof']

        # #IMPLIED attribute
        if 'sampleof' in elem.attrib:
            machine['sampleof'] = elem.attrib['sampleof']

        num_machines += 1

    elif event == 'start' and elem.tag == 'description':
        machine['description'] = unicode(elem.text)

    elif event == 'start' and elem.tag == 'year':
        machine['year'] = unicode(elem.text)

    elif event == 'start' and elem.tag == 'manufacturer':
        machine['manufacturer'] = unicode(elem.text)

    elif event == 'start' and elem.tag == 'input':
        # coins is #IMPLIED attribute
        if 'coins' in elem.attrib:
            machine['coins'] = int(elem.attrib['coins'])
            if machine['coins'] > 0: machine['haveCoin'] = True
            else:                    machine['haveCoin'] = False

    elif event == 'start' and elem.tag == 'driver':
        # status is #REQUIRED attribute
        machine['driver_status'] = unicode(elem.attrib['status'])

    elif event == 'end' and elem.tag == 'machine':
        elem.clear()
        machines[machine_name] = machine

    # --- Print something to prove we are doing stuff ---
    num_iteration += 1
    if num_iteration % 50000 == 0:
      print('Processed {0:10d} events ({1:6d} machines so far) ...'.format(num_iteration, num_machines))

    # --- Stop after some machines have been processed for debug ---
    if num_machines >= NUM_MACHINES: break
print('Processed {0} MAME XML events'.format(num_iteration))
print('Total number of machines {0}'.format(num_machines))

# -----------------------------------------------------------------------------
# Transform data
# -----------------------------------------------------------------------------
# Create one sets with parents and one dictionary clone : parent. This will
# accelerate computations a bit.
print('Making PClone list...')
parent_list = []
clone_dic = {}
for machine_name in machines:
    machine = machines[machine_name]
    # Exclude devices
    if machine['isdevice']: continue

    if machine['cloneof'] == u'':
        parent_list.append(machine_name)
    else:
        clone_dic[machine_name] = machine['cloneof']
parent_set = set(parent_list)
    
# --- Machine list ---
# A) Machines with Coin Slot and Non Mechanical
#
# This implementation is inefficient and slow, but it works.
#   1) Traverse list of machines.
#   2) If machine is a parent find all clones
#
# pclone_dic = { 'parent_name' : ['clone_name', 'clone_name', ...] , ...}
machines_pclone_dic = {}
print('Making Machine index...')
for parent_machine_name in parent_set:
    machine = machines[parent_machine_name]
    if machine['ismechanical']: continue
    if not machine['haveCoin']: continue
    # Make list of clones
    clone_list = []
    for clone_name, parent_name in clone_dic.iteritems():
        if parent_name == parent_machine_name:
            clone_list.append(clone_name)
    machines_pclone_dic[parent_machine_name] = clone_list

# --- NoCoin list ---
# A) Machines with No Coin Slot and Non Mechanical
nocoin_pclone_dic = {}
print('Making NoCoin index...')
for parent_machine_name in parent_set:
    machine = machines[parent_machine_name]
    if machine['ismechanical']: continue
    if machine['haveCoin']: continue
    # Make list of clones
    clone_list = []
    for clone_name, parent_name in clone_dic.iteritems():
        if parent_name == parent_machine_name:
            clone_list.append(clone_name)
    nocoin_pclone_dic[parent_machine_name] = clone_list

# --- Mechanical machines ---
# A) Mechanical Machines
mechanical_pclone_dic = {}
print('Making Mechanical index...')
for parent_machine_name in parent_set:
    machine = machines[parent_machine_name]
    if not machine['ismechanical']: continue
    # Make list of clones
    clone_list = []
    for clone_name, parent_name in clone_dic.iteritems():
        if parent_name == parent_machine_name:
            clone_list.append(clone_name)
    mechanical_pclone_dic[parent_machine_name] = clone_list

# -----------------------------------------------------------------------------
# Now write simplified JSON
# -----------------------------------------------------------------------------
print('Writing AML databases...')
fs_write_JSON(Main_DB_filename, machines)
fs_write_JSON(Machines_DB_filename, machines_pclone_dic)
fs_write_JSON(Machines_NoCoin_DB_filename, nocoin_pclone_dic)
fs_write_JSON(Machines_Mechanical_DB_filename, mechanical_pclone_dic)
