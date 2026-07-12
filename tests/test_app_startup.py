import unittest


class AppStartupTest(unittest.TestCase):
    def test_backend_app_imports_from_project_root(self):
        import backend.app as app_module

        self.assertTrue(hasattr(app_module, "app"))


if __name__ == "__main__":
    unittest.main()
