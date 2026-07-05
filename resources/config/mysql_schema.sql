-- SoftCart OLTP schema (MySQL 8.0).
-- Transactional source of truth for customers, orders, payments,
-- returns, promotions and sales channels.

CREATE DATABASE IF NOT EXISTS softcart_oltp;
USE softcart_oltp;

CREATE TABLE IF NOT EXISTS sales_channels (
    channel_id      INT UNSIGNED     NOT NULL,
    channel_name    VARCHAR(100)     NOT NULL,
    channel_type    VARCHAR(50)      NOT NULL,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id),
    UNIQUE KEY uq_channel_name (channel_name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS promotions (
    promotion_id    INT UNSIGNED     NOT NULL,
    promotion_code  VARCHAR(40)      NOT NULL,
    description     VARCHAR(255)     NOT NULL,
    discount_type   ENUM('percentage', 'fixed_amount') NOT NULL,
    discount_value  DECIMAL(10, 2)   NOT NULL,
    start_date      DATE             NOT NULL,
    end_date        DATE             NOT NULL,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (promotion_id),
    UNIQUE KEY uq_promotion_code (promotion_code),
    CONSTRAINT chk_promo_dates CHECK (end_date >= start_date),
    CONSTRAINT chk_promo_value CHECK (discount_value > 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS customers (
    customer_id     INT UNSIGNED     NOT NULL,
    first_name      VARCHAR(100)     NOT NULL,
    last_name       VARCHAR(100)     NOT NULL,
    email           VARCHAR(255)     NOT NULL,
    phone           VARCHAR(40)      NULL,
    signup_date     DATE             NOT NULL,
    created_at      DATETIME         NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id),
    UNIQUE KEY uq_customer_email (email),
    KEY idx_customer_signup (signup_date)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS customer_addresses (
    address_id      INT UNSIGNED     NOT NULL,
    customer_id     INT UNSIGNED     NOT NULL,
    address_type    ENUM('billing', 'shipping') NOT NULL,
    street          VARCHAR(255)     NOT NULL,
    city            VARCHAR(100)     NOT NULL,
    state           VARCHAR(100)     NOT NULL,
    country         VARCHAR(100)     NOT NULL,
    postal_code     VARCHAR(20)      NOT NULL,
    PRIMARY KEY (address_id),
    KEY idx_address_customer (customer_id),
    CONSTRAINT fk_address_customer FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id) ON DELETE CASCADE
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
    order_id        INT UNSIGNED     NOT NULL,
    customer_id     INT UNSIGNED     NOT NULL,
    channel_id      INT UNSIGNED     NOT NULL,
    promotion_id    INT UNSIGNED     NULL,
    order_date      DATETIME         NOT NULL,
    status          ENUM('processing', 'shipped', 'delivered', 'cancelled') NOT NULL,
    total_amount    DECIMAL(12, 2)   NOT NULL,
    PRIMARY KEY (order_id),
    KEY idx_order_customer (customer_id),
    KEY idx_order_date (order_date),
    KEY idx_order_channel (channel_id),
    CONSTRAINT fk_order_customer FOREIGN KEY (customer_id)
        REFERENCES customers (customer_id),
    CONSTRAINT fk_order_channel FOREIGN KEY (channel_id)
        REFERENCES sales_channels (channel_id),
    CONSTRAINT fk_order_promotion FOREIGN KEY (promotion_id)
        REFERENCES promotions (promotion_id),
    CONSTRAINT chk_order_total CHECK (total_amount >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
    order_item_id   INT UNSIGNED     NOT NULL,
    order_id        INT UNSIGNED     NOT NULL,
    product_id      VARCHAR(40)      NOT NULL COMMENT 'Business key into the MongoDB product catalog',
    quantity        INT UNSIGNED     NOT NULL,
    unit_price      DECIMAL(10, 2)   NOT NULL,
    discount_amount DECIMAL(10, 2)   NOT NULL DEFAULT 0.00,
    line_total      DECIMAL(12, 2)   NOT NULL,
    PRIMARY KEY (order_item_id),
    KEY idx_item_order (order_id),
    KEY idx_item_product (product_id),
    CONSTRAINT fk_item_order FOREIGN KEY (order_id)
        REFERENCES orders (order_id) ON DELETE CASCADE,
    CONSTRAINT chk_item_quantity CHECK (quantity > 0),
    CONSTRAINT chk_item_price CHECK (unit_price >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS payments (
    payment_id      INT UNSIGNED     NOT NULL,
    order_id        INT UNSIGNED     NOT NULL,
    payment_method  ENUM('credit_card', 'debit_card', 'paypal', 'apple_pay',
                         'gift_card', 'bank_transfer') NOT NULL,
    amount          DECIMAL(12, 2)   NOT NULL,
    payment_date    DATETIME         NOT NULL,
    status          ENUM('completed', 'pending', 'failed', 'refunded') NOT NULL,
    PRIMARY KEY (payment_id),
    KEY idx_payment_order (order_id),
    CONSTRAINT fk_payment_order FOREIGN KEY (order_id)
        REFERENCES orders (order_id) ON DELETE CASCADE,
    CONSTRAINT chk_payment_amount CHECK (amount >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS returns (
    return_id       INT UNSIGNED     NOT NULL,
    order_id        INT UNSIGNED     NOT NULL,
    order_item_id   INT UNSIGNED     NOT NULL,
    return_date     DATETIME         NOT NULL,
    quantity        INT UNSIGNED     NOT NULL,
    refund_amount   DECIMAL(12, 2)   NOT NULL,
    reason          VARCHAR(255)     NOT NULL,
    PRIMARY KEY (return_id),
    KEY idx_return_order (order_id),
    KEY idx_return_date (return_date),
    CONSTRAINT fk_return_order FOREIGN KEY (order_id)
        REFERENCES orders (order_id) ON DELETE CASCADE,
    CONSTRAINT fk_return_item FOREIGN KEY (order_item_id)
        REFERENCES order_items (order_item_id) ON DELETE CASCADE,
    CONSTRAINT chk_return_quantity CHECK (quantity > 0)
) ENGINE=InnoDB;
