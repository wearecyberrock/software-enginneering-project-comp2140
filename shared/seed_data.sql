-- Sample seed data for local testing across all 5 modules (COMP2140 Karmanjahni)

INSERT OR IGNORE INTO fx_rates (currency_code, rate_to_jmd) VALUES
  ('USD', 157.5000),
  ('JPY', 1.0500),
  ('SGD', 117.2000),
  ('THB', 4.5500),
  ('EUR', 171.0000);

INSERT OR IGNORE INTO vehicles
  (id, make, model, year, category, color, mileage_km, engine_cc, features, origin_country, photo_urls, base_foreign_price, base_currency, deposit_paid, is_deleted)
VALUES
  (1, 'Toyota', 'Tacoma Pickup', 2021, 'truck', 'Wine Red', 42000, 2700, 'Sunroof, Keyless Entry, Alloy Rims, 4WD', 'United States', '["/resources/design/assets/placeholder-vehicle.svg"]', 22500.00, 'USD', 1, 0),
  (2, 'Honda', 'Fit RS', 2020, 'car', 'Deep Purple', 31500, 1500, 'Keyless Entry, Alloy Rims, Push Start', 'Japan', '["/resources/design/assets/placeholder-vehicle.svg"]', 1450000.00, 'JPY', 1, 0),
  (3, 'Kubota', 'M7060 Farm Tractor', 2019, 'heavy_equipment', 'Orange', 1800, 3331, '4WD Utility Loader, Heavy Duty PTO', 'Japan', '["/resources/design/assets/placeholder-vehicle.svg"]', 28000.00, 'USD', 1, 0);

INSERT OR IGNORE INTO shipments
  (id, vehicle_id, bill_of_lading, status, eta_date, departure_date, delay_reason, is_deleted)
VALUES
  (1, 1, 'KJ-BOL-2026-001', 'In Transit', '2026-12-30', '2026-11-15', NULL, 0),
  (2, 2, 'KJ-BOL-2026-002', 'Delayed', '2026-12-18', '2026-11-01', 'Weather disruption in Pacific transit lane', 0),
  (3, 3, 'KJ-BOL-2026-003', 'Arrived', '2026-11-10', '2026-10-05', NULL, 0);
