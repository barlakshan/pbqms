from app import create_app
app = create_app('development')
for rule in app.url_map.iter_rules():
    if '/manager/officers' in str(rule) or '/manager/qr' in str(rule):
        print(rule)
