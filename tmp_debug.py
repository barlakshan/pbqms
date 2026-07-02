from app import create_app
from app.models import ServiceType
from app.extensions import db

app = create_app('testing')
print('uri', app.config['SQLALCHEMY_DATABASE_URI'])

with app.app_context():
    print('before create_all tables', db.engine.table_names())
    db.create_all()
    print('after create_all tables', db.engine.table_names())
    ServiceType.query.delete()
    db.session.commit()
    print('count after delete', ServiceType.query.count())
    s = ServiceType(code='AO', name='Account Opening', prefix='A', avg_service_min=12)
    db.session.add(s)
    db.session.commit()
    print('count after add', ServiceType.query.count())
    print('all', ServiceType.query.all())
