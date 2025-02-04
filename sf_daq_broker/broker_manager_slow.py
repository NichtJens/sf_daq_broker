import argparse
import logging

import bottle
import socket

from time import sleep

import json
from glob import glob
import os
import shutil

import epics

from slsdet import Jungfrau
from slsdet.enums import detectorSettings

from sf_daq_broker.broker_manager import allowed_detectors_beamline, ip_to_console
from sf_daq_broker.detector.power_on_detector import beamline_event_code

_logger = logging.getLogger(__name__)

conv_detector_settings = { detectorSettings.GAIN0: "normal", detectorSettings.HIGHGAIN0: "low_noise" }
conv_detector_settings_reverse = dict(zip(conv_detector_settings.values(), conv_detector_settings.keys()))

def register_rest_interface(app, manager):

    @app.post("/get_detector_settings")
    def get_detector_settings():
        return manager.get_detector_settings(request=bottle.request.json, remote_ip=bottle.request.remote_addr)

    @app.post("/set_detector_settings")
    def set_detector_settings():
        return manager.set_detector_settings(request=bottle.request.json, remote_ip=bottle.request.remote_addr)

    @app.post("/copy_user_files")
    def copy_user_files():
        return manager.copy_user_files(request=bottle.request.json, remote_ip=bottle.request.remote_addr)

    @app.error(500)
    def error_handler_500(error):
        bottle.response.content_type = 'application/json'
        bottle.response.status = 200

        error_text = str(error.exception)

        _logger.error(error_text)

        return json.dumps({"state": "error",
                           "status": error_text})

class DetectorManager(object):

    def get_detector_settings(self, request=None, remote_ip=None):

        if not request:
            return {"status" : "failed", "message" : "request parameters are empty"}

        if not remote_ip:
            return {"status" : "failed", "message" : "can not identify from which machine request were made"}

        beamline = ip_to_console(remote_ip)

        if not beamline:
            return {"status" : "failed", "message" : "can not determine from which console request came, rejected"}

        if beamline not in allowed_detectors_beamline:
            return {"status" : "failed", "message" : "request is made from beamline which doesnt have detectors"}

        detector_name = request.get("detector_name", None)
        if not detector_name:
            return {"status" : "failed", "message" : "no detector name in the request"}

        if detector_name not in allowed_detectors_beamline[beamline]:
                return {"status" : "failed", "message" : f"{detector_name} not belongs to the {beamline}"}

        detector_number = int(detector_name[2:4])
        detector = Jungfrau(detector_number)

        exptime = detector.exptime
        detector_mode_raw = detector.settings
        if detector_mode_raw in conv_detector_settings:
            detector_mode = conv_detector_settings[detector_mode_raw]
        else:
            detector_mode = "unknown"
        delay = detector.delay

        return {"status": "ok", "exptime": exptime, "detector_mode": detector_mode, "delay": delay}

    def set_detector_settings(self, request=None, remote_ip=None):

        if not request:
            return {"status" : "failed", "message" : "request parameters are empty"}

        if not remote_ip:
            return {"status" : "failed", "message" : "can not identify from which machine request were made"}

        beamline = ip_to_console(remote_ip)

        if not beamline:
            return {"status" : "failed", "message" : "can not determine from which console request came, rejected"}

        if beamline not in allowed_detectors_beamline:
            return {"status" : "failed", "message" : "request is made from beamline which doesnt have detectors"}

        detector_name = request.get("detector_name", None)
        if not detector_name:
            return {"status" : "failed", "message" : "no detector name in the request"}

        if detector_name not in allowed_detectors_beamline[beamline]:
                return {"status" : "failed", "message" : f"{detector_name} not belongs to the {beamline}"}

        exptime       = request.get("exptime", None)
        detector_mode = request.get("detector_mode", None)
        delay         = request.get("delay", None)

        event_code_pv_name = beamline_event_code[beamline]
        event_code_pv = epics.PV(event_code_pv_name)

        detector_number = int(detector_name[2:4])
        detector = Jungfrau(detector_number)

        # stop triggering of the beamline detectors
        try:
            event_code_pv.put(255) 
        except Exception as e:
            return  {"status" : "failed", "message" : "can not stop detector trigger"}

        #sleep few second to give epics a chance to switch code
        sleep(4)

        try:
            event_code = int(event_code_pv.get())
            if event_code != 255:
                return {"status" : "failed", "message" : "tried to stop detector trigger but failed"}
        except:
            return {"status" : "failed", "message" : f"getting strange return from timing system {event_code_pv.get()} {event_code_pv_name} {beamline}"}

        if exptime:
            detector.exptime = exptime
            print(f"setting exptime to {exptime}")

        if detector_mode:
            if detector_mode in conv_detector_settings_reverse:
                detector.settings = conv_detector_settings_reverse[detector_mode]
                print(f'settings detector settings to {conv_detector_settings_reverse[detector_mode]} ({detector_mode})')

        if delay:
            detector.delay = delay
            print(f"setting delay to {delay}")

        # start triggering
        event_code_pv.put(254)
       
        return {"status" : "ok"}

    def copy_user_files(self, request=None, remote_ip=None):

        if not request:
            return {"status" : "failed", "message" : "request parameters are empty"}

        if not remote_ip:
            return {"status" : "failed", "message" : "can not identify from which machine request were made"}

        beamline = ip_to_console(remote_ip)

        if not beamline:
            return {"status" : "failed", "message" : "can not determine from which console request came, rejected"}

        if beamline not in allowed_detectors_beamline:
            return {"status" : "failed", "message" : "request is made from beamline which doesnt have detectors"}

        if "pgroup" not in request:
            return {"status" : "failed", "message" : "no pgroup in request parameters"}
        pgroup = request["pgroup"]

        path_to_pgroup = f'/sf/{beamline}/data/{pgroup}/raw/'

        if os.path.exists(f'{path_to_pgroup}/run_info/CLOSED'):
            return {"status" : "failed", "message" : f'{path_to_pgroup} is closed for writing'}

        run_number = request.get("run_number", None)
        if run_number is None:
            return {"status" : "failed", "message" : "no run_number in request parameters"}

        list_data_directories_run = glob(f'{path_to_pgroup}/run{run_number:04}*')

        if len(list_data_directories_run) == 0:
            return {"status" : "failed", "message" : f"no such run {run_number} in the pgroup"}

        full_path = list_data_directories_run[0]

        target_directory = f'{full_path}/aux'

        if not os.path.exists(target_directory):
            try:
                os.mkdir(target_directory)
            except:
                return {"status" : "failed", "message" : "no permission or possibility to make aux sub-directory in pgroup space"}

        files_to_copy = request.get("files", [])

        error_files = []
        destination_file_path = []
        for file_to_copy in files_to_copy:
            try:
                dest = shutil.copy2(file_to_copy, target_directory)
                destination_file_path.append(dest)
            except:
                error_files.append(file_to_copy)

        return {"status" : "ok", "message" : "user file copy finished, check error_files list", "error_files" : error_files, "destination_file_path" : destination_file_path}


def start_server(rest_port):

    _logger.info(f"Starting detector server on port {rest_port} (rest-api)")

    app = bottle.Bottle()

    manager = DetectorManager()

    logging.getLogger("pika").setLevel(logging.WARNING)

    register_rest_interface(app, manager)

    _logger.info("Detector Server started.")

    try:
        hostname = socket.gethostname()
        _logger.info("Starting rest API on port %s host %s" % (rest_port, hostname) )
        bottle.run(app=app, host=hostname, port=rest_port)
    finally:
        pass


def run():
    parser = argparse.ArgumentParser(description='detector_settings')

    parser.add_argument("--rest_port", type=int, help="Port for REST api.", default=10003)

    parser.add_argument("--log_level", default='INFO',
                        choices=['CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG'],
                        help="Log level to use.")

    arguments = parser.parse_args()

    # Setup the logging level.
    logging.basicConfig(level=arguments.log_level, format='[%(levelname)s] %(message)s')

    start_server(rest_port=arguments.rest_port)


if __name__ == "__main__":
    run()
