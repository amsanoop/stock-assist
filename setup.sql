-- Stock Assist Database Setup
-- IMPORTANT: Update passwords and credentials before running!

CREATE DATABASE IF NOT EXISTS stockassist CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE stockassist;

-- Update root password (this should match MYSQL_ROOT_PASSWORD in docker-compose.yml)
-- CRITICAL: Change 'StockAssist2024!SecureDB' to your secure password
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY 'StockAssist2024!SecureDB';
ALTER USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'StockAssist2024!SecureDB';

-- Create application user (recommended for production)
-- CRITICAL: Change 'StockAssist2024!AppUser' to your secure password
CREATE USER IF NOT EXISTS 'stockassist_user'@'%' IDENTIFIED WITH mysql_native_password BY 'StockAssist2024!AppUser';
CREATE USER IF NOT EXISTS 'stockassist_user'@'localhost' IDENTIFIED WITH mysql_native_password BY 'StockAssist2024!AppUser';

-- Grant privileges to application user
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER ON stockassist.* TO 'stockassist_user'@'%';
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, DROP, INDEX, ALTER ON stockassist.* TO 'stockassist_user'@'localhost';

-- Grant root privileges (for admin operations)
GRANT ALL PRIVILEGES ON *.* TO 'root'@'localhost' WITH GRANT OPTION;
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

-- Flush privileges to apply changes
FLUSH PRIVILEGES;

-- Create initial admin user (OPTIONAL - update credentials)
-- IMPORTANT: Change email and password before running!
-- INSERT INTO user (email, password_hash, name, subscription_id, created_at)
-- VALUES ('admin@yourdomain.com', 'CHANGE_THIS_PASSWORD_HASH', 'Admin User', 4, NOW());

-- Note: To generate password hash, use:
-- python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your_password'))"