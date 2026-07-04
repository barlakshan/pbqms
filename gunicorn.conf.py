import multiprocessing

bind = "127.0.0.1:8000"
workers = max(2, multiprocessing.cpu_count() // 2 + 1)
worker_class = "gthread"
threads = 4
timeout = 120
keepalive = 5
accesslog = "-"
errorlog = "-"
capture_output = True
