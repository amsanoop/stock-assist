import multiprocessing


loglevel = 'critical'  
errorlog = '/dev/null' 
accesslog = '/dev/null'
capture_output = False 

bind = "0.0.0.0:80"
backlog = 2048

workers = multiprocessing.cpu_count() * 2 + 1
worker_class = 'eventlet'
worker_connections = 10000
timeout = 300
keepalive = 5

accesslog = '-'
errorlog = '-'
loglevel = 'info'

proc_name = 'stockassist'

daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

websocket_ping_interval = 10
websocket_ping_timeout = 20
websocket_max_message_size = 65536

session_ttl = 1800 
session_cleanup_interval = 300 

max_requests = 1000
max_requests_jitter = 50
graceful_timeout = 30
keep_alive = 5

keyfile = None
certfile = None

forwarded_allow_ips = '*' 
secure_scheme_headers = {'X-FORWARDED-PROTOCOL': 'ssl', 'X-FORWARDED-PROTO': 'https', 'X-FORWARDED-SSL': 'on'} 