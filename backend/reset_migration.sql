BEGIN;

-- Running upgrade a5b1c6285b42 -> 954a9e3b2f31

CREATE TABLE password_reset_tokens (
    id UUID NOT NULL, 
    user_id UUID NOT NULL, 
    token_digest VARCHAR(64) NOT NULL, 
    credential_fingerprint VARCHAR(64) NOT NULL, 
    created_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL, 
    used_at TIMESTAMP WITH TIME ZONE, 
    invalidated_at TIMESTAMP WITH TIME ZONE, 
    PRIMARY KEY (id), 
    FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, 
    CONSTRAINT uq_password_reset_tokens_token_digest UNIQUE (token_digest)
);

CREATE INDEX ix_password_reset_tokens_user_id ON password_reset_tokens (user_id);

CREATE INDEX ix_password_reset_tokens_expires_at ON password_reset_tokens (expires_at);

UPDATE alembic_version SET version_num='954a9e3b2f31' WHERE alembic_version.version_num = 'a5b1c6285b42';

COMMIT;

