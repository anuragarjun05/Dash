"""Tests for utils.qr_generator module."""

import unittest
from utils.qr_generator import generate_qr_code, haversine_distance, verify_location


class TestHaversineDistance(unittest.TestCase):
    """Tests for the haversine great-circle distance function."""

    def test_same_point_returns_zero(self):
        dist = haversine_distance(28.6139, 77.2090, 28.6139, 77.2090)
        self.assertAlmostEqual(dist, 0.0, places=2)

    def test_known_distance(self):
        # ~111 km between consecutive integer latitudes at the equator
        dist = haversine_distance(0.0, 0.0, 1.0, 0.0)
        self.assertAlmostEqual(dist, 111_195, delta=200)

    def test_symmetry(self):
        d1 = haversine_distance(28.6139, 77.2090, 19.0760, 72.8777)
        d2 = haversine_distance(19.0760, 72.8777, 28.6139, 77.2090)
        self.assertAlmostEqual(d1, d2, places=2)


class TestVerifyLocation(unittest.TestCase):
    """Tests for the location verification function."""

    def test_within_radius(self):
        is_ok, dist = verify_location(28.6139, 77.2090, 28.6139, 77.2090, 100)
        self.assertTrue(is_ok)
        self.assertAlmostEqual(dist, 0.0, places=2)

    def test_outside_radius(self):
        # Delhi to Mumbai — well outside 100 m
        is_ok, dist = verify_location(28.6139, 77.2090, 19.0760, 72.8777, 100)
        self.assertFalse(is_ok)
        self.assertGreater(dist, 1_000_000)  # > 1000 km

    def test_boundary_within(self):
        # A very small offset (~11 m) should be within 100 m
        is_ok, _ = verify_location(28.6139, 77.2090, 28.6140, 77.2090, 100)
        self.assertTrue(is_ok)

    def test_boundary_outside(self):
        # A large offset should be outside a tiny radius
        is_ok, _ = verify_location(28.6139, 77.2090, 28.6200, 77.2090, 10)
        self.assertFalse(is_ok)


class TestGenerateQRCode(unittest.TestCase):
    """Tests for QR code generation."""

    def test_returns_tuple(self):
        result = generate_qr_code(
            "http://localhost:8050", "PUMP-A-101", 28.6139, 77.2090, 100
        )
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)

    def test_url_contains_parameters(self):
        url, _ = generate_qr_code(
            "http://localhost:8050", "PUMP-A-101", 28.6139, 77.2090, 100
        )
        self.assertIn("equipment_id=PUMP-A-101", url)
        self.assertIn("lat=28.613900", url)
        self.assertIn("lng=77.209000", url)
        self.assertIn("radius=100", url)
        self.assertTrue(url.startswith("http://localhost:8050/maintenance?"))

    def test_base64_image_format(self):
        _, b64 = generate_qr_code(
            "http://localhost:8050", "PUMP-A-101", 28.6139, 77.2090, 100
        )
        self.assertTrue(b64.startswith("data:image/png;base64,"))

    def test_different_equipment_produces_different_urls(self):
        url1, _ = generate_qr_code(
            "http://localhost:8050", "PUMP-A-101", 28.6139, 77.2090, 100
        )
        url2, _ = generate_qr_code(
            "http://localhost:8050", "MOTOR-B-202", 28.6139, 77.2090, 100
        )
        self.assertNotEqual(url1, url2)


if __name__ == "__main__":
    unittest.main()
