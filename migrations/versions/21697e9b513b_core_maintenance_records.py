"""core maintenance records

Revision ID: 21697e9b513b
Revises: 
Create Date: 2026-11-04 07:25:19.485732

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '21697e9b513b'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('teams',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.CheckConstraint("role IN ('tenant', 'owner', 'staff')", name='user_role'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'role')
    )
    op.create_table('credentials',
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('token_hash')
    )
    op.create_index(op.f('ix_credentials_user_id'), 'credentials', ['user_id'], unique=False)
    op.create_table('memberships',
    sa.Column('team_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('user_role', sa.String(length=16), nullable=False),
    sa.Column('role', sa.String(length=16), nullable=False),
    sa.CheckConstraint("role IN ('coordinator', 'member')", name='membership_role'),
    sa.CheckConstraint("user_role = 'staff'", name='member_is_staff'),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.ForeignKeyConstraint(['user_id', 'user_role'], ['users.id', 'users.role'], ),
    sa.PrimaryKeyConstraint('team_id', 'user_id'),
    sa.UniqueConstraint('team_id', 'user_id', 'role')
    )
    op.create_table('properties',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('address', sa.String(length=250), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('owner_role', sa.String(length=16), nullable=False),
    sa.Column('team_id', sa.Uuid(), nullable=True),
    sa.CheckConstraint("owner_role = 'owner'", name='property_owner_role'),
    sa.ForeignKeyConstraint(['owner_id', 'owner_role'], ['users.id', 'users.role'], ),
    sa.ForeignKeyConstraint(['team_id'], ['teams.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'team_id')
    )
    op.create_index(op.f('ix_properties_owner_id'), 'properties', ['owner_id'], unique=False)
    op.create_index(op.f('ix_properties_team_id'), 'properties', ['team_id'], unique=False)
    op.create_table('incidents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('property_id', sa.Uuid(), nullable=False),
    sa.Column('team_id', sa.Uuid(), nullable=False),
    sa.Column('coordinator_id', sa.Uuid(), nullable=False),
    sa.Column('coordinator_role', sa.String(length=16), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.CheckConstraint("coordinator_role = 'coordinator'", name='incident_coordinator_role'),
    sa.CheckConstraint("status = 'open'", name='incident_status'),
    sa.ForeignKeyConstraint(['property_id', 'team_id'], ['properties.id', 'properties.team_id'], ),
    sa.ForeignKeyConstraint(['team_id', 'coordinator_id', 'coordinator_role'], ['memberships.team_id', 'memberships.user_id', 'memberships.role'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'property_id')
    )
    op.create_table('tenancies',
    sa.Column('property_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_role', sa.String(length=16), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.CheckConstraint("tenant_role = 'tenant'", name='tenancy_tenant_role'),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ),
    sa.ForeignKeyConstraint(['tenant_id', 'tenant_role'], ['users.id', 'users.role'], ),
    sa.PrimaryKeyConstraint('property_id', 'tenant_id')
    )
    op.create_table('vendors',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('specialty', sa.String(length=100), nullable=False),
    sa.Column('contact_email', sa.String(length=200), nullable=False),
    sa.Column('property_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'property_id')
    )
    op.create_index(op.f('ix_vendors_property_id'), 'vendors', ['property_id'], unique=False)
    op.create_table('warranties',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('property_id', sa.Uuid(), nullable=False),
    sa.Column('asset', sa.String(length=100), nullable=False),
    sa.Column('provider', sa.String(length=100), nullable=False),
    sa.Column('starts_on', sa.Date(), nullable=False),
    sa.Column('ends_on', sa.Date(), nullable=False),
    sa.Column('terms', sa.Text(), nullable=False),
    sa.CheckConstraint('ends_on >= starts_on', name='warranty_dates'),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_warranties_property_id'), 'warranties', ['property_id'], unique=False)
    op.create_table('maintenance_history',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('property_id', sa.Uuid(), nullable=False),
    sa.Column('vendor_id', sa.Uuid(), nullable=True),
    sa.Column('performed_on', sa.Date(), nullable=False),
    sa.Column('summary', sa.Text(), nullable=False),
    sa.Column('cost', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.CheckConstraint('cost >= 0', name='history_cost'),
    sa.ForeignKeyConstraint(['property_id'], ['properties.id'], ),
    sa.ForeignKeyConstraint(['vendor_id', 'property_id'], ['vendors.id', 'vendors.property_id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_maintenance_history_property_id'), 'maintenance_history', ['property_id'], unique=False)
    op.create_table('maintenance_requests',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('property_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('incident_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('category', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('idempotency_key', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("category IN ('plumbing', 'electrical', 'heating', 'general')", name='request_category'),
    sa.CheckConstraint("status IN ('submitted', 'acknowledged')", name='request_status'),
    sa.CheckConstraint('length(trim(description)) BETWEEN 1 AND 5000', name='request_description'),
    sa.CheckConstraint('length(trim(title)) BETWEEN 1 AND 200', name='request_title'),
    sa.ForeignKeyConstraint(['incident_id', 'property_id'], ['incidents.id', 'incidents.property_id'], ),
    sa.ForeignKeyConstraint(['property_id', 'tenant_id'], ['tenancies.property_id', 'tenancies.tenant_id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tenant_id', 'idempotency_key', name='request_idempotency')
    )
    op.create_index(op.f('ix_maintenance_requests_incident_id'), 'maintenance_requests', ['incident_id'], unique=False)
    op.create_index(op.f('ix_maintenance_requests_property_id'), 'maintenance_requests', ['property_id'], unique=False)
    op.create_index(op.f('ix_maintenance_requests_tenant_id'), 'maintenance_requests', ['tenant_id'], unique=False)
    op.execute("""
        CREATE FUNCTION preserve_request_original() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF ROW(NEW.id, NEW.property_id, NEW.tenant_id, NEW.title, NEW.description,
                   NEW.category, NEW.idempotency_key, NEW.created_at)
               IS DISTINCT FROM
               ROW(OLD.id, OLD.property_id, OLD.tenant_id, OLD.title, OLD.description,
                   OLD.category, OLD.idempotency_key, OLD.created_at) THEN
                RAISE EXCEPTION 'Original request fields are immutable' USING ERRCODE = '23514';
            END IF;
            IF NEW.status <> OLD.status AND NOT
               (OLD.status = 'submitted' AND NEW.status = 'acknowledged') THEN
                RAISE EXCEPTION 'Invalid request state transition' USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $$;
        CREATE TRIGGER request_original_guard BEFORE UPDATE ON maintenance_requests
        FOR EACH ROW EXECUTE FUNCTION preserve_request_original();
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP TRIGGER request_original_guard ON maintenance_requests")
    op.execute("DROP FUNCTION preserve_request_original()")
    op.drop_index(op.f('ix_maintenance_requests_tenant_id'), table_name='maintenance_requests')
    op.drop_index(op.f('ix_maintenance_requests_property_id'), table_name='maintenance_requests')
    op.drop_index(op.f('ix_maintenance_requests_incident_id'), table_name='maintenance_requests')
    op.drop_table('maintenance_requests')
    op.drop_index(op.f('ix_maintenance_history_property_id'), table_name='maintenance_history')
    op.drop_table('maintenance_history')
    op.drop_index(op.f('ix_warranties_property_id'), table_name='warranties')
    op.drop_table('warranties')
    op.drop_index(op.f('ix_vendors_property_id'), table_name='vendors')
    op.drop_table('vendors')
    op.drop_table('tenancies')
    op.drop_table('incidents')
    op.drop_index(op.f('ix_properties_team_id'), table_name='properties')
    op.drop_index(op.f('ix_properties_owner_id'), table_name='properties')
    op.drop_table('properties')
    op.drop_table('memberships')
    op.drop_index(op.f('ix_credentials_user_id'), table_name='credentials')
    op.drop_table('credentials')
    op.drop_table('users')
    op.drop_table('teams')
