from ctypes import *

FOLDER_MOD = 100000
FILE_MOD = 1000
FILE_EXTENSION = ".bin"
# Module X * Y * 2 (16 bits)
MODULE_N_BYTES = 1024 * 512 * 2


class BufferBinaryFormat(Structure):
    _pack_ = 1
    _fields_ = [
        ("FORMAT_MARKER", c_char),
        ("pulse_id", c_uint64),
        ("frame_index", c_uint64),
        ("daq_rec", c_uint64),
        ("n_recv_packets", c_uint64),
        ("module_id", c_uint64),
        ("data", c_byte * MODULE_N_BYTES)
    ]


BUFFER_FRAME_BYTES = sizeof(BufferBinaryFormat)
DATA_FRAME_BYTES = MODULE_N_BYTES
META_FRAME_BYTES = BUFFER_FRAME_BYTES - DATA_FRAME_BYTES


class ModuleReader(object):
    def __init__(self, ram_buffer, detector_folder, module_id):
        self.ram_buffer = ram_buffer
        self.detector_folder = detector_folder
        self.module_id = module_id

        self._file = None
        self._filename = None

    def load_frame(self, pulse_id):
        pulse_filename, pulse_index = self._get_pulse_id_location(pulse_id)

        if pulse_filename != self._filename:
            self._open_file(pulse_filename)

        n_bytes_offset = pulse_index * BUFFER_FRAME_BYTES
        self._file.seek(n_bytes_offset)

        meta_buffer, data_buffer = self.ram_buffer.get_buffers(self.module_id, pulse_id)

        meta_bytes = self._file.readinto(meta_buffer)
        if meta_bytes != META_FRAME_BYTES:
            raise ValueError("Read frame %d, got %d meta bytes but expected %d bytes." %
                             (pulse_id, meta_bytes, META_FRAME_BYTES))

        data_bytes = self._file.readinto(data_buffer)
        if data_bytes != DATA_FRAME_BYTES:
            raise ValueError("Read frame %d, got %d data bytes but expected %d bytes." %
                             (pulse_id, data_bytes, DATA_FRAME_BYTES))

    def _get_pulse_id_location(self, pulse_id):
        folder_base = int((pulse_id // FOLDER_MOD) * FOLDER_MOD)
        file_base = int((pulse_id // FILE_MOD) * FILE_MOD)

        filename = "%s/%s/%s/%s%s" % (self.detector_folder,
                                      self.module_name,
                                      folder_base,
                                      file_base,
                                      FILE_EXTENSION)

        # Index inside the data_file for the provided pulse_id.
        pulse_id_index = pulse_id - file_base

        return filename, pulse_id_index

    def _open_file(self, new_filename):
        self.close_file()

        # buffering=0 turns buffering off
        self._file = open(new_filename, mode='rb', buffering=0)
        self._filename = new_filename

    def close_file(self):
        if self._file:
            self._file.close()


class DetectorReader(object):
    def __init__(self, ram_buffer, detector_folder, n_modules):
        self.ram_buffer = ram_buffer
        self.detector_folder = detector_folder
        self.n_modules = n_modules

    def start_reading(self, start_pulse_id, end_pulse_id):
        pass

    def close(self):
        pass