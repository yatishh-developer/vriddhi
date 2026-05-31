from repositories.dashboard_repository import DashboardRepository


class DashboardService:

    @staticmethod
    def get_summary(
        db,
        current_user
    ):

        total_products = DashboardRepository.get_total_products(
            db,
            current_user.business_id
        )

        total_customers = DashboardRepository.get_total_customers(
            db,
            current_user.business_id
        )

        total_transactions = DashboardRepository.get_total_transactions(
            db,
            current_user.business_id
        )

        total_sales = DashboardRepository.get_total_sales(
            db,
            current_user.business_id
        )

        low_stock_products = DashboardRepository.get_low_stock_products(
            db,
            current_user.business_id
        )

        return {
            "total_products": total_products,
            "total_customers": total_customers,
            "total_transactions": total_transactions,
            "total_sales": total_sales,
            "low_stock_products": len(low_stock_products)
        }