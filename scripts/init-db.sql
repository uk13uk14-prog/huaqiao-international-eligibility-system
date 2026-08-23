-- Initialize PostgreSQL databases for huaqiao project
CREATE DATABASE huaqiao_free;
CREATE DATABASE huaqiao_saas;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE huaqiao_free TO huaqiao;
GRANT ALL PRIVILEGES ON DATABASE huaqiao_saas TO huaqiao;
