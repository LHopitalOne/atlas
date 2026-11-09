import unittest
from unittest import mock

from payroll.hr_client import HrClient


class HrClientTest(unittest.TestCase):
    def test_salary_band_builds_url(self):
        client = HrClient("http://hr.test/")
        response = mock.Mock(status_code=200)
        response.json.return_value = {"band": "B2", "min": 1, "max": 2, "currency": "EUR"}
        with mock.patch.object(client._session, "get", return_value=response) as get:
            self.assertEqual(client.salary_band(7)["band"], "B2")
        get.assert_called_once_with("http://hr.test/api/employees/7/salary-band/", timeout=5.0)


if __name__ == "__main__":
    unittest.main()
