"""Initial schema — People's Bank QEMS v1.0

Revision ID: 001_initial
"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table('branches',
        sa.Column('id',         sa.Integer,      primary_key=True),
        sa.Column('name',       sa.String(120),  nullable=False),
        sa.Column('code',       sa.String(10),   unique=True, nullable=False),
        sa.Column('address',    sa.Text),
        sa.Column('city',       sa.String(80)),
        sa.Column('phone',      sa.String(20)),
        sa.Column('is_active',  sa.Boolean,      default=True),
        sa.Column('created_at', sa.DateTime,     server_default=sa.func.now()),
    )

    op.create_table('service_types',
        sa.Column('id',              sa.Integer, primary_key=True),
        sa.Column('code',            sa.String(5),  unique=True, nullable=False),
        sa.Column('name',            sa.String(80), nullable=False),
        sa.Column('prefix',          sa.String(2),  nullable=False),
        sa.Column('avg_service_min', sa.Integer,    default=10),
        sa.Column('is_active',       sa.Boolean,    default=True),
    )

    op.execute("""
        INSERT INTO service_types (code, name, prefix, avg_service_min) VALUES
        ('AO', 'Account Opening',  'A', 12),
        ('AC', 'Account Closing',  'C',  8),
        ('FD', 'Fixed Deposits',   'F', 10),
        ('LN', 'Loans',            'L', 15),
        ('OT', 'Other',            'O', 10)
    """)

    op.create_table('users',
        sa.Column('id',            sa.Integer,     primary_key=True),
        sa.Column('branch_id',     sa.Integer,     sa.ForeignKey('branches.id')),
        sa.Column('employee_id',   sa.String(20),  unique=True, nullable=False),
        sa.Column('full_name',     sa.String(120), nullable=False),
        sa.Column('email',         sa.String(120), unique=True, nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('role',          sa.Enum('admin','branch_manager','lobby_officer','loan_officer',
                                           name='userrole'), nullable=False),
        sa.Column('is_active',     sa.Boolean,     default=True),
        sa.Column('last_login',    sa.DateTime),
        sa.Column('created_at',    sa.DateTime,    server_default=sa.func.now()),
    )

    op.create_table('customers',
        sa.Column('id',         sa.Integer,    primary_key=True),
        sa.Column('full_name',  sa.String(120), nullable=False),
        sa.Column('mobile',     sa.String(20),  unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime,    server_default=sa.func.now()),
    )

    op.create_table('counters',
        sa.Column('id',            sa.Integer,  primary_key=True),
        sa.Column('branch_id',     sa.Integer,  sa.ForeignKey('branches.id'), nullable=False),
        sa.Column('user_id',       sa.Integer,  sa.ForeignKey('users.id')),
        sa.Column('label',         sa.String(20), nullable=False),
        sa.Column('service_scope', sa.String(20)),
        sa.Column('is_active',     sa.Boolean,  default=True),
    )

    op.create_table('queue_tokens',
        sa.Column('id',                 sa.Integer,  primary_key=True),
        sa.Column('branch_id',          sa.Integer,  sa.ForeignKey('branches.id'),       nullable=False),
        sa.Column('customer_id',        sa.Integer,  sa.ForeignKey('customers.id'),      nullable=False),
        sa.Column('service_type_id',    sa.Integer,  sa.ForeignKey('service_types.id'),  nullable=False),
        sa.Column('counter_id',         sa.Integer,  sa.ForeignKey('counters.id')),
        sa.Column('served_by',          sa.Integer,  sa.ForeignKey('users.id')),
        sa.Column('token_number',       sa.String(10), nullable=False),
        sa.Column('custom_reason',      sa.Text),
        sa.Column('status',             sa.Enum('waiting','called','serving','completed','no_show','skipped',
                                                name='tokenstatus'), default='waiting'),
        sa.Column('is_priority',        sa.Boolean,  default=False),
        sa.Column('priority_reason',    sa.Enum('none','elderly','pregnant','disabled',
                                                name='priorityreason'), default='none'),
        sa.Column('estimated_wait_min', sa.Integer,  default=0),
        sa.Column('issued_at',          sa.DateTime, server_default=sa.func.now()),
        sa.Column('called_at',          sa.DateTime),
        sa.Column('served_at',          sa.DateTime),
        sa.Column('completed_at',       sa.DateTime),
        sa.Column('queue_date',         sa.Date,     server_default=sa.func.current_date()),
        sa.UniqueConstraint('branch_id','service_type_id','token_number','queue_date',
                             name='uq_token_per_service_per_day'),
    )

    op.create_table('sms_logs',
        sa.Column('id',                  sa.Integer,  primary_key=True),
        sa.Column('token_id',            sa.Integer,  sa.ForeignKey('queue_tokens.id'), nullable=False),
        sa.Column('sms_type',            sa.Enum('confirmation','call_notification', name='smstype')),
        sa.Column('mobile',              sa.String(20), nullable=False),
        sa.Column('message',             sa.Text,       nullable=False),
        sa.Column('status',              sa.Enum('pending','sent','failed', name='smsstatus'), default='pending'),
        sa.Column('provider_message_id', sa.String(80)),
        sa.Column('sent_at',             sa.DateTime),
        sa.Column('created_at',          sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table('audit_logs',
        sa.Column('id',         sa.Integer,  primary_key=True),
        sa.Column('user_id',    sa.Integer,  sa.ForeignKey('users.id')),
        sa.Column('token_id',   sa.Integer,  sa.ForeignKey('queue_tokens.id')),
        sa.Column('action',     sa.String(80), nullable=False),
        sa.Column('payload',    sa.JSON),
        sa.Column('ip_address', sa.String(45)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table('satisfaction_ratings',
        sa.Column('id',       sa.Integer, primary_key=True),
        sa.Column('token_id', sa.Integer, sa.ForeignKey('queue_tokens.id'),
                   nullable=False, unique=True),
        sa.Column('rating',   sa.Integer, nullable=False),
        sa.Column('comment',  sa.Text),
        sa.Column('rated_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Performance indexes
    op.create_index('ix_tokens_branch_date_status',  'queue_tokens', ['branch_id','queue_date','status'])
    op.create_index('ix_tokens_customer',            'queue_tokens', ['customer_id'])
    op.create_index('ix_tokens_served_by',           'queue_tokens', ['served_by'])
    op.create_index('ix_tokens_priority',            'queue_tokens', ['is_priority'])
    op.create_index('ix_audit_user',                 'audit_logs',   ['user_id'])
    op.create_index('ix_audit_created',              'audit_logs',   ['created_at'])
    op.create_index('ix_customers_mobile',           'customers',    ['mobile'])

def downgrade():
    for idx in ['ix_customers_mobile','ix_audit_created','ix_audit_user',
                'ix_tokens_priority','ix_tokens_served_by','ix_tokens_customer',
                'ix_tokens_branch_date_status']:
        try: op.drop_index(idx)
        except: pass
    for tbl in ['satisfaction_ratings','audit_logs','sms_logs','queue_tokens',
                'counters','customers','users','service_types','branches']:
        op.drop_table(tbl)
