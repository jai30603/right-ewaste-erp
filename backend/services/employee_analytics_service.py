from repositories import employee_report_repository


class EmployeeAnalyticsService:

    @staticmethod
    def get_analytics():
        return employee_report_repository.get_analytics_data()
