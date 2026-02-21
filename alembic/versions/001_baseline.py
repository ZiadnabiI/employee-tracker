"""Initial baseline schema

Revision ID: 001_baseline
Revises: (none)
Create Date: 2026-02-21

This is the baseline migration representing the existing database schema.
All tables already exist in production — this migration is a no-op for
existing databases and only creates tables for fresh installations.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Companies
    op.create_table(
        "companies",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), unique=True, index=True),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("subscription_plan", sa.String(), server_default="free"),
        sa.Column("subscription_status", sa.String(), server_default="active"),
        sa.Column("subscription_end_date", sa.DateTime(), nullable=True),
        sa.Column("stripe_customer_id", sa.String(), nullable=True),
        sa.Column("max_employees", sa.Integer(), server_default="5"),
        sa.Column("screenshot_frequency", sa.Integer(), server_default="600"),
        sa.Column("dlp_enabled", sa.Integer(), server_default="0"),
        sa.Column("slack_webhook_url", sa.String(), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        if_not_exists=True,
    )

    # Departments
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String()),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id")),
        if_not_exists=True,
    )

    # Supervisors
    op.create_table(
        "supervisors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(), unique=True, index=True),
        sa.Column("password_hash", sa.String()),
        sa.Column("name", sa.String()),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id")),
        sa.Column("is_super_admin", sa.Integer(), server_default="0"),
        sa.Column("role", sa.String(), server_default="owner"),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("password_reset_token", sa.String(), nullable=True),
        sa.Column("password_reset_expires", sa.DateTime(), nullable=True),
        if_not_exists=True,
    )

    # Employees
    op.create_table(
        "employees",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), index=True),
        sa.Column("activation_key", sa.String(), unique=True, index=True),
        sa.Column("hardware_id", sa.String(), nullable=True),
        sa.Column("is_active", sa.Integer(), server_default="0"),
        sa.Column("department", sa.String(), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("email", sa.String(), unique=True, index=True, nullable=True),
        sa.Column("password_hash", sa.String(), nullable=True),
        sa.Column("invite_token", sa.String(), index=True, nullable=True),
        sa.Column("invite_expires", sa.DateTime(), nullable=True),
        sa.Column("is_registered", sa.Integer(), server_default="0"),
        sa.Column("last_heartbeat", sa.DateTime(), nullable=True),
        sa.Column("pending_screenshot", sa.Integer(), server_default="0"),
        if_not_exists=True,
    )

    # Activity Logs
    op.create_table(
        "logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("employee_name", sa.String()),
        sa.Column("status", sa.String()),
        sa.Column("timestamp", sa.DateTime()),
        if_not_exists=True,
    )

    # App Usage Logs
    op.create_table(
        "app_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("employee_name", sa.String(), index=True),
        sa.Column("app_name", sa.String()),
        sa.Column("window_title", sa.String()),
        sa.Column("duration_seconds", sa.Integer(), server_default="0"),
        sa.Column("timestamp", sa.DateTime()),
        if_not_exists=True,
    )

    # Screenshots
    op.create_table(
        "screenshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("employee_name", sa.String(), index=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("blob_url", sa.String()),
        sa.Column("manual_request", sa.Integer(), server_default="0"),
        sa.Column("timestamp", sa.DateTime()),
        if_not_exists=True,
    )

    # Auth Tokens
    op.create_table(
        "auth_tokens",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(255), unique=True, index=True),
        sa.Column("supervisor_id", sa.Integer(), sa.ForeignKey("supervisors.id")),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id")),
        sa.Column("is_super_admin", sa.Integer(), server_default="0"),
        sa.Column("expires", sa.DateTime()),
        sa.Column("created_at", sa.DateTime()),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("auth_tokens")
    op.drop_table("screenshots")
    op.drop_table("app_logs")
    op.drop_table("logs")
    op.drop_table("employees")
    op.drop_table("supervisors")
    op.drop_table("departments")
    op.drop_table("companies")
