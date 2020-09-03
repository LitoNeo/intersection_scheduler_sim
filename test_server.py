#!/usr/bin/env python
# --coding:utf-8--

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib import parse

# curl -v -i http://127.0.0.1:8989/?foo=bar

class _handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = parse.urlparse(self.path) # ParseResult(scheme='', netloc='', path='/', params='', query='foo=bar', fragment='')
        message_parts = [
            'CLIENT VALUES:',
            'client_address={} ({})'.format(self.client_address, self.address_string()),
            'command={}'.format(self.command),  # GET
            'path={}'.format(self.path),  # /?foo=bar 即ip:port外所有内容组成的字符串
            'real_path={}'.format(parsed_path.path),  # /根目录
            'query={}'.format(parsed_path.query),  # foo=bar
            'request_version={}'.format(self.request_version),  # HTTP/1.1
            "",
            'SERVER VALUES:',
            'server_version={}'.format(self.server_version),  # BaseHTTP/0.6
            'sys_version={}'.format(self.sys_version),  # Python/3.7.4
            'protocol_version={}'.format(self.protocol_version),  # HTTP/1.0
            "",
            'HEADERS RECEIVED',
        ]
        for name, value in sorted(self.headers.items()):
            message_parts.append('{}={}'.format(name, value))  # Accept/Host/User-Agent等
        message_parts.append('')
        message = '\r\n'.join(message_parts)

        # 所有文本先被组装起来，然后写入self.wfile,返回给client
        self.send_response(200)
        self.send_header('Content-Type',
                         'text/plain; charset=utf-8')
        self.end_headers()

        self.wfile.write(message.encode('utf-8'))


if __name__ == '__main__':
    server = HTTPServer(('localhost', 8989), _handler)
    print("start server")
    server.serve_forever()
