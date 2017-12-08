import os
import uuid

import numpy as np
from flask import Flask, request, send_from_directory
from flask.ext.jsonpify import jsonify
from flask_restful import Resource, Api

import chemkin.nasa
import chemkin.parser
from . import webserver as ws

import chemkin.plot


class Session(Resource):
    def post(self):
        sid = str(uuid.uuid1())
        data = request.json['data']
        print(data)
        folder = "/tmp/chemkin/webserver/{}".format(sid)
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "data.xml"), "w") as f:
            f.write(data)
        try:
            nasa = chemkin.nasa.NASACoeffs()
            data_parser = chemkin.parser.DataParser()
            # parse the data file and return an instance of ReactionData class
            reaction_data = data_parser.parse_file(os.path.join(folder, "data.xml"), nasa)
            return {'status': 'success', 'id': sid, 'species': reaction_data.species}
        except Exception as e:
            return {'status': 'failed', 'reason': 'Failed to parse given xml file ({})'.format(str(e))}


class Rates(Resource):
    def post(self, sid):
        folder = "/tmp/chemkin/webserver/{}".format(sid)
        nasa = chemkin.nasa.NASACoeffs()
        # create a data parser class
        data_parser = chemkin.parser.DataParser()
        # parse the data file and return an instance of ReactionData class
        reaction_data = data_parser.parse_file(os.path.join(folder, "data.xml"), nasa)

        try:
            conc = [0] * len(reaction_data.species)

            for i, sp in enumerate(reaction_data.species):
                conc[i] = float(request.json[sp])

            T = float(request.json['_temp'])

            progress_rates = reaction_data.get_progress_rate(conc, T)  # type: np.ndarray
            reaction_rates = reaction_data.get_reaction_rate(progress_rates)
            ks = reaction_data.get_k(T)
            result = {
                "status": "success",
                'progress_rates': progress_rates.tolist(),
                'reaction_rates': reaction_rates.tolist(),
                'ks': ks.tolist(),
                'species': reaction_data.species,
            }
            return jsonify(result)
        except Exception as e:
            return {'status': 'failed', 'reason': 'Failed to get rates ({})'.format(str(e))}


class Plots(Resource):
    def post(self, sid, tlow, thigh):
        folder = "/tmp/chemkin/webserver/{}".format(sid)
        nasa = chemkin.nasa.NASACoeffs()
        # create a data parser class
        data_parser = chemkin.parser.DataParser()
        # parse the data file and return an instance of ReactionData class
        reaction_data = data_parser.parse_file(os.path.join(folder, "data.xml"), nasa)

        try:
            tlow = float(tlow)
            thigh = float(thigh)

            conc = [0] * len(reaction_data.species)

            for i, sp in enumerate(reaction_data.species):
                conc[i] = float(request.json[sp])

            T = float(request.json['_temp'])

            T_range, progress_rate_range, reaction_rate_range, current_T, species, pc, rc = chemkin.plot.range_data_collection(
                reaction_data, conc, tlow, thigh, T)

            pic_width = 600 // 75
            pic_length = 400 // 75

            progress_plot = chemkin.plot.progress_rate_plot_generation(T_range, progress_rate_range, current_T, pc,
                                                                       pic_width,
                                                                       pic_length)

            reaction_plot = chemkin.plot.reaction_rate_plot_generation(T_range, reaction_rate_range, current_T, rc,
                                                                       species,
                                                                       pic_width,
                                                                       pic_length)

            return {
                "status": "success",
                'progress_rates': progress_plot,
                'reaction_rates': reaction_plot
            }
        except Exception as e:
            return {'status': 'failed', 'reason': 'Failed to get plots ({})'.format(str(e))}


class WebServer:
    def __init__(self, port):
        self.port = port
        self.app = Flask("chemkin web server")
        self.api = Api(self.app)
        self.api.add_resource(Session, '/session')
        self.api.add_resource(Rates, '/rates/<sid>')
        self.api.add_resource(Plots, '/plots/<sid>/<tlow>/<thigh>')
        path = os.path.dirname(ws.__file__)
        self.web_folder = os.path.join(path, "web")

    def start(self):
        @self.app.route('/<path:path>')
        def send_static(path):
            return send_from_directory(self.web_folder, path)

        @self.app.route('/')
        def send_index():
            return send_from_directory(self.web_folder, "index.html")

        self.app.run(port=self.port)
