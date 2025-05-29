from alembic import op
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError, ProgrammingError

def safe_create_table(table_name, columns, constraints=None):
    """Safely create a table if it doesn't exist.
    
    Args:
        table_name (str): The name of the table to create
        columns (list): List of SQLAlchemy Column objects
        constraints (list, optional): List of SQLAlchemy Constraint objects
    
    Returns:
        bool: True if the table was created, False if it already exists
    """
    try:
        if constraints:
            op.create_table(table_name, *columns, *constraints)
        else:
            op.create_table(table_name, *columns)
        return True
    except OperationalError as e:
        if "already exists" in str(e):
            print(f"Table {table_name} already exists, skipping creation")
            return False
        else:
            raise e

def safe_drop_table(table_name):
    """Safely drop a table if it exists.
    
    Args:
        table_name (str): The name of the table to drop
    
    Returns:
        bool: True if the table was dropped, False if it doesn't exist
    """
    try:
        op.drop_table(table_name)
        return True
    except (OperationalError, ProgrammingError) as e:
        if "doesn't exist" in str(e) or "Unknown table" in str(e):
            print(f"Table {table_name} doesn't exist, skipping drop")
            return False
        else:
            raise e

def safe_create_index(table_name, index_name, columns, unique=False):
    """Safely create an index if it doesn't exist.
    
    Args:
        table_name (str): The name of the table
        index_name (str): The name of the index to create
        columns (list): List of column names to include in the index
        unique (bool, optional): Whether the index should be unique
    
    Returns:
        bool: True if the index was created, False if it already exists
    """
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.create_index(index_name, columns, unique=unique)
        return True
    except OperationalError as e:
        if "Duplicate key name" in str(e):
            print(f"Index {index_name} already exists on table {table_name}, skipping creation")
            return False
        else:
            raise e

def safe_drop_index(table_name, index_name):
    """Safely drop an index if it exists.
    
    Args:
        table_name (str): The name of the table
        index_name (str): The name of the index to drop
    
    Returns:
        bool: True if the index was dropped, False if it doesn't exist
    """
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_index(index_name)
        return True
    except (OperationalError, ProgrammingError) as e:
        if "doesn't exist" in str(e) or "Can't DROP" in str(e):
            print(f"Index {index_name} doesn't exist on table {table_name}, skipping drop")
            return False
        else:
            raise e

def safe_drop_constraint(table_name, constraint_name, type_):
    """Safely drop a constraint if it exists.
    
    Args:
        table_name (str): The name of the table
        constraint_name (str): The name of the constraint to drop
        type_ (str): The type of constraint ('foreignkey', 'unique', 'primary', etc.)
    
    Returns:
        bool: True if the constraint was dropped, False if it doesn't exist
    """
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.drop_constraint(constraint_name, type_=type_)
        return True
    except (OperationalError, ProgrammingError) as e:
        if "doesn't exist" in str(e) or "Can't DROP" in str(e):
            print(f"Constraint {constraint_name} doesn't exist on table {table_name}, skipping drop")
            return False
        else:
            raise e

def safe_create_foreign_key(table_name, constraint_name, referent_table, local_cols, remote_cols, ondelete=None, onupdate=None):
    """Safely create a foreign key constraint if it doesn't exist.
    
    Args:
        table_name (str): The name of the table
        constraint_name (str): The name of the constraint to create
        referent_table (str): The name of the table being referenced
        local_cols (list): List of column names in the local table
        remote_cols (list): List of column names in the referent table
        ondelete (str, optional): ON DELETE behavior
        onupdate (str, optional): ON UPDATE behavior
    
    Returns:
        bool: True if the constraint was created, False if it already exists
    """
    try:
        with op.batch_alter_table(table_name, schema=None) as batch_op:
            batch_op.create_foreign_key(
                constraint_name, 
                referent_table, 
                local_cols, 
                remote_cols, 
                ondelete=ondelete, 
                onupdate=onupdate
            )
        return True
    except OperationalError as e:
        if "already exists" in str(e):
            print(f"Foreign key {constraint_name} already exists on table {table_name}, skipping creation")
            return False
        else:
            raise e 