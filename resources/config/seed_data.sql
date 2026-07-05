-- Static reference data for a fresh SoftCart OLTP database.
-- Sales channels are stable reference data; the Python generator writes the
-- same rows idempotently (see src/main/models/sales_channel.py).

USE softcart_oltp;

INSERT INTO sales_channels (channel_id, channel_name, channel_type) VALUES
    (1, 'SoftCart Web',        'web'),
    (2, 'SoftCart Mobile App', 'mobile'),
    (3, 'Amazon Marketplace',  'marketplace'),
    (4, 'eBay Marketplace',    'marketplace'),
    (5, 'Instagram Shop',      'social'),
    (6, 'Partner Kiosk',       'retail')
ON DUPLICATE KEY UPDATE
    channel_name = VALUES(channel_name),
    channel_type = VALUES(channel_type);
