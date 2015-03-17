#!/usr/bin/env python
# coding: utf-8
# Copyright (c) 2013-2015 Abram Hindle, Michael Raypold
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
import flask
from flask import Flask, request
from flask_sockets import Sockets
import gevent
from gevent import queue
import time
import json
import os

app = Flask(__name__, static_url_path='')
sockets = Sockets(app)
app.debug = True

class World:
    def __init__(self):
        self.clear()
        # we've got listeners now!
        self.listeners = list()

    def add_set_listener(self, listener):
        self.listeners.append( listener )

    def remove_listener(self, listener):
        self.listeners.remove( listener )

    def update(self, entity, key, value):
        entry = self.space.get(entity,dict())
        entry[key] = value
        self.space[entity] = entry
        self.update_listeners( entity )

    def set(self, entity, data):
        self.space[entity] = data
        self.update_listeners( entity )

    def update_listeners(self, entity):
        '''update the set listeners'''
        for listener in self.listeners:
            try:
                set_listener(listener, entity, self.get(entity))
            except:
                pass

    def clear(self):
        self.space = dict()

    def get(self, entity):
        return self.space.get(entity,dict())

    def world(self):
        return self.space

myWorld = World()

def set_listener(ws, entity, data ):
    ''' do something with the update ! '''
    msg = {}
    msg[entity] = data

    # jsonify not working here...Have to use json.dumps
    ws.send(json.dumps(msg))

# myWorld.add_set_listener( set_listener )

@app.route('/')
def hello():
    '''Return something coherent here.. perhaps redirect to /static/index.html '''
    return app.send_static_file('index.html')

def read_ws(ws):
    '''A greenlet function that reads from the websocket and updates the world'''
    try:
        while True:
            msg = ws.receive()
            print 'received %s' %(msg)

            if msg:
                packet = json.loads(msg)
                for k,v in packet.items():
                    myWorld.set(k, v)
    except:
        pass
    return None

@sockets.route('/subscribe')
def subscribe_socket(ws):
    '''Fufill the websocket URL of /subscribe, every update notify the
       websocket and read updates from the websocket

    Source https://github.com/abramhindle/WebSocketsExamples/blob/master/chat.py
    '''
    myWorld.add_set_listener(ws)
    ws.send(json.dumps(myWorld.world()))
    g = gevent.spawn( read_ws, ws )

    try:
        while True:
            # Blocking
            time.sleep(1)
    except Exception as e:
        print "WS Error %s" % e
    finally:
        myWorld.remove_listener(ws)
        gevent.kill(g)

    return None

def flask_post_json():
    '''Ah the joys of frameworks! They do so much work for you
       that they get in the way of sane operation!'''
    if (request.json != None):
        return request.json
    elif (request.data != None and request.data != ''):
        return json.loads(request.data)
    else:
        return json.loads(request.form.keys()[0])

@app.route("/entity/<entity>", methods=['POST','PUT'])
def update(entity):
    '''update the entities via this interface'''
    json = request.get_json(force = True, silent = True, cache = True)
    myWorld.set(entity, json)

    return jsonify(**myWorld.get(entity))

@app.route("/world", methods=['POST','GET'])
def world():
    '''you should probably return the world here'''
    return jsonify(**myWorld.world())

@app.route("/entity/<entity>")
def get_entity(entity):
    '''This is the GET version of the entity interface, return a representation of the entity'''
    return jsonify(**myWorld.get(entity))

@app.route("/clear", methods=['POST','GET'])
def clear():
    '''Clear the world out!'''
    myWorld.clear()

    if request.method == 'POST':
        return jsonify(**myWorld.world())

    if request.method == 'GET':
        return redirect(url_for('hello'))

if __name__ == "__main__":
    ''' This doesn't work well anymore:
        pip install gunicorn
        and run
        gunicorn -k flask_sockets.worker sockets:app
    '''
    app.run()
