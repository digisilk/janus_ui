import struct
import re

class DEXParser:
    def __init__(self, dex_data_or_path):
        if isinstance(dex_data_or_path, str):
            with open(dex_data_or_path, 'rb') as f:
                self.data = f.read()
        else:
            self.data = dex_data_or_path
        self.header = {}
        self.string_ids = []
        self.strings = []

    def parse(self):
        self.parse_header()
        self.parse_string_ids()
        self.parse_strings()

    def parse_header(self):
        header_data = self.data[:112]
        self.header = {
            'magic': header_data[:8],
            'checksum': struct.unpack('<I', header_data[8:12])[0],
            'signature': header_data[12:32],
            'file_size': struct.unpack('<I', header_data[32:36])[0],
            'header_size': struct.unpack('<I', header_data[36:40])[0],
            'endian_tag': struct.unpack('<I', header_data[40:44])[0],
            'link_size': struct.unpack('<I', header_data[44:48])[0],
            'link_off': struct.unpack('<I', header_data[48:52])[0],
            'map_off': struct.unpack('<I', header_data[52:56])[0],
            'string_ids_size': struct.unpack('<I', header_data[56:60])[0],
            'string_ids_off': struct.unpack('<I', header_data[60:64])[0],
            'type_ids_size': struct.unpack('<I', header_data[64:68])[0],
            'type_ids_off': struct.unpack('<I', header_data[68:72])[0],
            'proto_ids_size': struct.unpack('<I', header_data[72:76])[0],
            'proto_ids_off': struct.unpack('<I', header_data[76:80])[0],
            'field_ids_size': struct.unpack('<I', header_data[80:84])[0],
            'field_ids_off': struct.unpack('<I', header_data[84:88])[0],
            'method_ids_size': struct.unpack('<I', header_data[88:92])[0],
            'method_ids_off': struct.unpack('<I', header_data[92:96])[0],
            'class_defs_size': struct.unpack('<I', header_data[96:100])[0],
            'class_defs_off': struct.unpack('<I', header_data[100:104])[0],
            'data_size': struct.unpack('<I', header_data[104:108])[0],
            'data_off': struct.unpack('<I', header_data[108:112])[0],
        }

    def parse_string_ids(self):
        offset = self.header['string_ids_off']
        for i in range(self.header['string_ids_size']):
            string_data_off = struct.unpack('<I', self.data[offset:offset + 4])[0]
            self.string_ids.append(string_data_off)
            offset += 4

    def parse_strings(self):
        url_regex = re.compile(r'https?://\S+')
        for string_data_off in self.string_ids:
            size, offset = self.read_uleb128(string_data_off)
            string_data = self.data[offset:offset + size].decode('utf-8', errors='replace')
            if url_regex.search(string_data):
                self.strings.append(string_data)

    def read_uleb128(self, offset):
        result = 0
        shift = 0
        size = 0
        while True:
            byte = self.data[offset]
            offset += 1
            size += 1
            result |= (byte & 0x7f) << shift
            if byte & 0x80 == 0:
                break
            shift += 7
        return result, offset

    def get_strings(self):
        return self.strings