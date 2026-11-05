-- ONLINE SHOP: database prototype (works in SQLite and MySQL 8)

CREATE TABLE Customer (
  customer_id   INT PRIMARY KEY,
  full_name     VARCHAR(100) NOT NULL,
  email         VARCHAR(100) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  phone         VARCHAR(20),
  registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Category (
  category_id   INT PRIMARY KEY,
  category_name VARCHAR(50) NOT NULL UNIQUE,
  description   VARCHAR(255),
  is_active     BOOLEAN DEFAULT TRUE
);

CREATE TABLE Product (
  product_id     INT PRIMARY KEY,
  category_id    INT NOT NULL,
  product_name   VARCHAR(150) NOT NULL,
  description    TEXT,
  price          DECIMAL(10,2) NOT NULL CHECK (price > 0),
  stock_quantity INT NOT NULL CHECK (stock_quantity >= 0),
  FOREIGN KEY (category_id) REFERENCES Category(category_id) ON DELETE RESTRICT
);

CREATE TABLE Orders (
  order_id         INT PRIMARY KEY,
  customer_id      INT NOT NULL,
  order_date       DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  order_status     VARCHAR(20) NOT NULL
                   CHECK (order_status IN ('Pending','Paid','Shipped','Delivered','Cancelled')),
  shipping_address VARCHAR(255) NOT NULL,
  total_amount     DECIMAL(10,2) NOT NULL CHECK (total_amount >= 0),
  FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE RESTRICT
);

CREATE TABLE Order_Item (
  order_item_id INT PRIMARY KEY,
  order_id      INT NOT NULL,
  product_id    INT NOT NULL,
  quantity      INT NOT NULL CHECK (quantity > 0),
  unit_price    DECIMAL(10,2) NOT NULL CHECK (unit_price > 0),
  UNIQUE (order_id, product_id),
  FOREIGN KEY (order_id)   REFERENCES Orders(order_id)     ON DELETE RESTRICT,
  FOREIGN KEY (product_id) REFERENCES Product(product_id)  ON DELETE RESTRICT
);

CREATE TABLE Payment (
  payment_id     INT PRIMARY KEY,
  order_id       INT NOT NULL UNIQUE,
  payment_method VARCHAR(20) NOT NULL
                 CHECK (payment_method IN ('Card','Bank transfer','Cash on delivery')),
  amount         DECIMAL(10,2) NOT NULL CHECK (amount > 0),
  payment_status VARCHAR(20) NOT NULL
                 CHECK (payment_status IN ('Pending','Paid','Failed','Refunded')),
  paid_at        DATETIME,
  FOREIGN KEY (order_id) REFERENCES Orders(order_id) ON DELETE RESTRICT
);

-- SAMPLE DATA
INSERT INTO Customer (customer_id, full_name, email, password_hash, phone) VALUES
 (101, 'Aigerim K.', 'aigerim@example.com', 'hash_a1', '+7 700 111 11 11'),
 (102, 'Dana S.',    'dana@example.com',    'hash_b2', '+7 700 222 22 22'),
 (103, 'Timur A.',   'timur@example.com',   'hash_c3', NULL);

INSERT INTO Category (category_id, category_name, description) VALUES
 (1, 'Electronics', 'Gadgets and accessories'),
 (2, 'Stationery',  'Notebooks and pens'),
 (3, 'Home',        'Things for home and desk');

INSERT INTO Product (product_id, category_id, product_name, description, price, stock_quantity) VALUES
 (10, 1, 'USB-C Cable',    'Charging cable 1 m',  12.00, 120),
 (12, 1, 'Wireless Mouse', 'Silent mouse',        25.00,   6),
 (20, 2, 'Notebook A5',    '80 pages',             3.00, 200),
 (30, 3, 'Water Bottle',   '500 ml',               8.00,  45),
 (31, 3, 'Desk Lamp',      'LED lamp',            20.00,   8);

INSERT INTO Orders (order_id, customer_id, order_status, shipping_address, total_amount) VALUES
 (5001, 101, 'Paid',      'Almaty, Abay Ave 1',    800.00),
 (5002, 102, 'Delivered', 'Almaty, Satpaev St 5',  612.00),
 (5003, 101, 'Cancelled', 'Almaty, Abay Ave 1',    125.00),
 (5004, 103, 'Paid',      'Astana, Mira St 9',     640.00);

INSERT INTO Order_Item (order_item_id, order_id, product_id, quantity, unit_price) VALUES
 (9001, 5001, 12, 20, 25.00),
 (9002, 5001, 31, 15, 20.00),
 (9003, 5002, 10, 37, 12.00),
 (9004, 5002, 30, 21,  8.00),
 (9005, 5003, 12,  5, 25.00),
 (9006, 5004, 12, 22, 25.00),
 (9007, 5004, 20, 30,  3.00);

INSERT INTO Payment (payment_id, order_id, payment_method, amount, payment_status, paid_at) VALUES
 (7001, 5001, 'Card',             800.00, 'Paid', CURRENT_TIMESTAMP),
 (7002, 5002, 'Cash on delivery', 612.00, 'Paid', CURRENT_TIMESTAMP),
 (7003, 5004, 'Bank transfer',    640.00, 'Paid', CURRENT_TIMESTAMP);

-- QUERY: best-selling products, revenue and stock left
SELECT p.product_name,
       c.category_name,
       SUM(oi.quantity)                 AS units_sold,
       SUM(oi.quantity * oi.unit_price) AS revenue,
       p.stock_quantity
FROM Order_Item oi
JOIN Orders   o ON oi.order_id   = o.order_id
JOIN Product  p ON oi.product_id = p.product_id
JOIN Category c ON p.category_id = c.category_id
WHERE o.order_status <> 'Cancelled'
GROUP BY p.product_id, p.product_name, c.category_name, p.stock_quantity
ORDER BY units_sold DESC
LIMIT 5;


--ADDRESS TABLE 

CREATE TABLE Address (
  address_id   INT PRIMARY KEY,
  customer_id  INT NOT NULL,
  city         VARCHAR(50)  NOT NULL,
  address_line VARCHAR(255) NOT NULL,
  is_default   BOOLEAN NOT NULL DEFAULT FALSE,
  FOREIGN KEY (customer_id) REFERENCES Customer(customer_id) ON DELETE RESTRICT
);

INSERT INTO Address (address_id, customer_id, city, address_line, is_default) VALUES
 (201, 101, 'Almaty', 'Abay Ave 1',    TRUE),
 (202, 101, 'Almaty', 'Dostyk Ave 20', FALSE),
 (203, 102, 'Almaty', 'Satpaev St 5',  TRUE),
 (204, 103, 'Astana', 'Mira St 9',     TRUE);



ALTER TABLE Orders ADD COLUMN address_id INT;
ALTER TABLE Orders ADD FOREIGN KEY (address_id) REFERENCES Address(address_id) ON DELETE RESTRICT;

UPDATE Orders SET address_id = 201 WHERE order_id IN (5001, 5003);
UPDATE Orders SET address_id = 203 WHERE order_id = 5002;
UPDATE Orders SET address_id = 204 WHERE order_id = 5004;