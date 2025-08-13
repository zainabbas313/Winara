from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import hashlib
import json
import logging

from interface.Irepositories.analytics_repository import IAnalyticsRepository
from interface.Iservices.analytics_service import IAnalyticsService
from repositories.analytics_repository import AnalyticsRepository
from schemas.analytics import (
    AnalyticsScope, DashboardAnalytics, ReportRequest, ReportResponse,
    BidPerformanceReport, FinancialReport, OperationalReport,
    KPIData, ChartDataPoint, VerticalBreakdown, TeamPerformance, MemberPerformance
)
from schemas.common import ExportRequest, ExportResponse
from models.models import UserRole
import io
import csv
import pandas as pd

logger = logging.getLogger(__name__)


class AnalyticsService(IAnalyticsService):
    def __init__(self):
        self.repository: IAnalyticsRepository = AnalyticsRepository()

    def get_dashboard_analytics(self, db: Session, scope_data: AnalyticsScope,
                               requesting_user_id: UUID, requesting_user_role: UserRole,
                               requesting_user_team_id: Optional[UUID] = None) -> DashboardAnalytics:
        """Get dashboard analytics with role-based access control."""
        try:
            # Validate access
            if not self.validate_analytics_access(
                scope_data.scope, requesting_user_role,
                scope_data.team_id, scope_data.user_id,
                requesting_user_team_id, requesting_user_id
            ):
                raise PermissionError("Insufficient permissions for requested scope")

            # Generate cache key
            cache_key = self.generate_analytics_cache_key("dashboard", {
                "scope": scope_data.scope,
                "team_id": str(scope_data.team_id) if scope_data.team_id else None,
                "user_id": str(scope_data.user_id) if scope_data.user_id else None,
                "range": scope_data.range,
                "from_date": scope_data.from_date.isoformat() if scope_data.from_date else None,
                "to_date": scope_data.to_date.isoformat() if scope_data.to_date else None
            })

            # Check cache first
            cached_data = self.get_cached_analytics(cache_key)
            if cached_data:
                return DashboardAnalytics(**cached_data)

            # Apply role-based filtering
            filtered_team_id, filtered_user_id = self._apply_role_filters(
                requesting_user_role, requesting_user_team_id, requesting_user_id,
                scope_data.team_id, scope_data.user_id
            )

            # Calculate date range
            date_from, date_to = self._calculate_date_range(
                scope_data.range, scope_data.from_date, scope_data.to_date
            )

            # Get KPIs
            kpi_data = self.repository.get_dashboard_kpis(
                db, scope_data.scope, filtered_team_id, filtered_user_id,
                date_from, date_to
            )

            # Get chart data
            bids_over_time = self.repository.get_bids_over_time(
                db, filtered_team_id, filtered_user_id, date_from, date_to
            )

            revenue_over_time = self.repository.get_revenue_over_time(
                db, filtered_team_id, filtered_user_id, date_from, date_to
            )

            vertical_breakdown = self.repository.get_vertical_breakdown(
                db, filtered_team_id, filtered_user_id, date_from, date_to
            )

            # Transform data to response format
            kpis = KPIData(
                total_bids=kpi_data.get('total_bids', 0),
                wins=kpi_data.get('wins', 0),
                win_rate=kpi_data.get('win_rate', Decimal('0')),
                connect_spend=kpi_data.get('connect_spend', Decimal('0')),
                revenue=kpi_data.get('revenue', Decimal('0')),
                profit_margin=kpi_data.get('profit_margin', Decimal('0'))
            )

            charts = {
                'bids_over_time': bids_over_time,
                'revenue_over_time': revenue_over_time,
                'vertical_breakdown': vertical_breakdown
            }

            result = DashboardAnalytics(kpis=kpis, charts=charts)

            # Cache the result
            self.cache_analytics_results(cache_key, result.dict(), ttl_minutes=15)

            return result

        except Exception as e:
            logger.error(f"Error getting dashboard analytics: {e}")
            raise

    def generate_report(self, db: Session, report_request: ReportRequest,
                       requesting_user_id: UUID, requesting_user_role: UserRole,
                       requesting_user_team_id: Optional[UUID] = None) -> ReportResponse:
        """Generate analytics report with role-based filtering."""
        try:
            # Extract filters
            filters = report_request.filters or {}
            team_id = UUID(filters.get('team_id')) if filters.get('team_id') else None
            date_from = filters.get('date_from')
            date_to = filters.get('date_to')

            # Apply role-based filtering
            filtered_team_id, _ = self._apply_role_filters(
                requesting_user_role, requesting_user_team_id, requesting_user_id,
                team_id, None
            )

            # Generate appropriate report based on type
            if report_request.type == "bid_performance":
                data = self.repository.get_bid_performance_report(
                    db, filtered_team_id, date_from, date_to
                )
            elif report_request.type == "financial":
                data = self.repository.get_financial_report(
                    db, filtered_team_id, date_from, date_to
                )
            elif report_request.type == "operational":
                data = self.repository.get_operational_report(
                    db, filtered_team_id, date_from, date_to
                )
            else:
                raise ValueError(f"Invalid report type: {report_request.type}")

            return ReportResponse(
                type=report_request.type,
                generated_at=datetime.utcnow(),
                data=data
            )

        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise

    def export_analytics(self, db: Session, export_request: ExportRequest,
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None) -> ExportResponse:
        """Export analytics data in various formats."""
        try:
            # Generate report data first
            report_request = ReportRequest(
                type=export_request.export_type,
                filters=export_request.filters
            )
            
            report_response = self.generate_report(
                db, report_request, requesting_user_id, 
                requesting_user_role, requesting_user_team_id
            )

            # Export in requested format
            if export_request.format == "csv":
                file_content = self._export_to_csv(report_response.data)
                content_type = "text/csv"
            elif export_request.format == "xlsx":
                file_content = self._export_to_xlsx(report_response.data)
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif export_request.format == "pdf":
                file_content = self._export_to_pdf(report_response.data)
                content_type = "application/pdf"
            elif export_request.format == "json":
                file_content = json.dumps(report_response.data, indent=2, default=str)
                content_type = "application/json"
            else:
                raise ValueError(f"Unsupported export format: {export_request.format}")

            filename = f"{export_request.export_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{export_request.format}"

            return ExportResponse(
                filename=filename,
                content_type=content_type,
                file_size=len(file_content.encode()) if isinstance(file_content, str) else len(file_content),
                download_url=f"/analytics/download/{filename}",  # This would need file storage implementation
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )

        except Exception as e:
            logger.error(f"Error exporting analytics: {e}")
            raise

    def get_bid_performance_report(self, db: Session, team_id: Optional[UUID] = None,
                                  date_from: Optional[date] = None, date_to: Optional[date] = None,
                                  requesting_user_role: UserRole = None,
                                  requesting_user_team_id: Optional[UUID] = None) -> BidPerformanceReport:
        """Generate detailed bid performance report."""
        try:
            # Apply role-based filtering
            filtered_team_id, _ = self._apply_role_filters(
                requesting_user_role, requesting_user_team_id, None, team_id, None
            )

            # Get report data from repository
            report_data = self.repository.get_bid_performance_report(
                db, filtered_team_id, date_from, date_to
            )

            # Transform to schema format
            summary = KPIData(**report_data['summary'])
            
            team_breakdown = [
                TeamPerformance(**team) for team in report_data['team_breakdown']
            ]
            
            member_breakdown = [
                MemberPerformance(**member) for member in report_data['member_breakdown']
            ]
            
            vertical_breakdown = [
                VerticalBreakdown(**vertical) for vertical in report_data['vertical_breakdown']
            ]
            
            trends = [
                ChartDataPoint(date=trend['date'], bids=trend['bids'], wins=trend['wins'])
                for trend in report_data['trends']
            ]

            return BidPerformanceReport(
                summary=summary,
                team_breakdown=team_breakdown,
                member_breakdown=member_breakdown,
                vertical_breakdown=vertical_breakdown,
                trends=trends
            )

        except Exception as e:
            logger.error(f"Error generating bid performance report: {e}")
            raise

    def get_financial_report(self, db: Session, team_id: Optional[UUID] = None,
                            date_from: Optional[date] = None, date_to: Optional[date] = None,
                            requesting_user_role: UserRole = None,
                            requesting_user_team_id: Optional[UUID] = None) -> FinancialReport:
        """Generate financial report with revenue, costs, and profitability."""
        try:
            # Apply role-based filtering
            filtered_team_id, _ = self._apply_role_filters(
                requesting_user_role, requesting_user_team_id, None, team_id, None
            )

            # Get report data from repository
            report_data = self.repository.get_financial_report(
                db, filtered_team_id, date_from, date_to
            )

            # Transform to schema format
            monthly_trends = [
                ChartDataPoint(date=trend['date'], revenue=Decimal(str(trend['revenue'])))
                for trend in report_data['monthly_trends']
            ]

            return FinancialReport(
                revenue_summary=report_data['revenue_summary'],
                cost_summary=report_data['cost_summary'],
                profit_summary=report_data['profit_summary'],
                receivables_summary=report_data.get('receivables_summary', {}),
                monthly_trends=monthly_trends
            )

        except Exception as e:
            logger.error(f"Error generating financial report: {e}")
            raise

    def get_operational_report(self, db: Session, team_id: Optional[UUID] = None,
                              date_from: Optional[date] = None, date_to: Optional[date] = None,
                              requesting_user_role: UserRole = None,
                              requesting_user_team_id: Optional[UUID] = None) -> OperationalReport:
        """Generate operational efficiency report."""
        try:
            # Apply role-based filtering
            filtered_team_id, _ = self._apply_role_filters(
                requesting_user_role, requesting_user_team_id, None, team_id, None
            )

            # Get report data from repository
            report_data = self.repository.get_operational_report(
                db, filtered_team_id, date_from, date_to
            )

            # Get team utilization data
            team_performance = self.repository.get_team_performance(db, date_from, date_to)
            team_utilization = [
                TeamPerformance(**team) for team in team_performance
                if not filtered_team_id or team['team_id'] == filtered_team_id
            ]

            return OperationalReport(
                productivity_metrics=report_data['productivity_metrics'],
                efficiency_metrics=report_data['efficiency_metrics'],
                quality_metrics=report_data['quality_metrics'],
                team_utilization=team_utilization
            )

        except Exception as e:
            logger.error(f"Error generating operational report: {e}")
            raise

    def validate_analytics_access(self, scope: str, requesting_user_role: UserRole,
                                 requested_team_id: Optional[UUID] = None,
                                 requested_user_id: Optional[UUID] = None,
                                 requesting_user_team_id: Optional[UUID] = None,
                                 requesting_user_id: Optional[UUID] = None) -> bool:
        """Validate if user has access to requested analytics scope."""
        try:
            if requesting_user_role == UserRole.ADMIN:
                return True

            if scope == "admin":
                return requesting_user_role == UserRole.ADMIN

            if scope == "team":
                if requesting_user_role == UserRole.SUB_ADMIN:
                    return not requested_team_id or requested_team_id == requesting_user_team_id
                return False

            if scope == "member":
                if requesting_user_role == UserRole.ADMIN:
                    return True
                if requesting_user_role == UserRole.SUB_ADMIN:
                    # Sub-admin can view member data for their team members
                    # Additional validation would be needed to check if requested user is in same team
                    return True
                if requesting_user_role == UserRole.MEMBER:
                    return not requested_user_id or requested_user_id == requesting_user_id

            return False

        except Exception as e:
            logger.error(f"Error validating analytics access: {e}")
            return False

    def get_performance_insights(self, db: Session, team_id: Optional[UUID] = None,
                                user_id: Optional[UUID] = None,
                                requesting_user_role: UserRole = None) -> Dict[str, Any]:
        """Get AI-powered performance insights and recommendations."""
        try:
            insights = {
                "key_insights": [],
                "recommendations": [],
                "benchmarks": {},
                "trends": {}
            }

            # Get win rate trends
            win_rate_trends = self.repository.get_win_rate_trends(db, team_id, user_id)
            
            # Analyze trends
            if len(win_rate_trends) >= 7:
                recent_avg = sum(t['win_rate'] for t in win_rate_trends[-7:]) / 7
                older_avg = sum(t['win_rate'] for t in win_rate_trends[-14:-7]) / 7 if len(win_rate_trends) >= 14 else recent_avg
                
                if recent_avg > older_avg * 1.1:
                    insights["key_insights"].append({
                        "type": "positive_trend",
                        "message": f"Win rate has improved by {((recent_avg / older_avg - 1) * 100):.1f}% in the last week",
                        "impact": "high"
                    })
                elif recent_avg < older_avg * 0.9:
                    insights["key_insights"].append({
                        "type": "negative_trend", 
                        "message": f"Win rate has declined by {((1 - recent_avg / older_avg) * 100):.1f}% in the last week",
                        "impact": "high"
                    })
                    insights["recommendations"].append({
                        "action": "Review recent bid quality and targeting strategy",
                        "priority": "high"
                    })

            # Get cost analysis
            cost_analysis = self.repository.get_cost_analysis(db, team_id, user_id)
            
            if cost_analysis.get('cost_per_win', 0) > 50:  # Arbitrary threshold
                insights["recommendations"].append({
                    "action": "Consider optimizing connect usage - cost per win is high",
                    "priority": "medium"
                })

            # Get ROI analysis
            roi_analysis = self.repository.get_roi_analysis(db, team_id, user_id)
            
            if roi_analysis.get('roi_percentage', 0) < 100:
                insights["recommendations"].append({
                    "action": "Focus on higher-value projects to improve ROI",
                    "priority": "high"
                })

            insights["benchmarks"] = {
                "industry_avg_win_rate": 15.0,  # Industry benchmark
                "cost_per_win_benchmark": 30.0,
                "roi_benchmark": 200.0
            }

            insights["trends"] = {
                "win_rate_trends": win_rate_trends,
                "cost_trends": cost_analysis,
                "roi_trends": roi_analysis
            }

            return insights

        except Exception as e:
            logger.error(f"Error getting performance insights: {e}")
            return {}

    def get_predictive_analytics(self, db: Session, team_id: Optional[UUID] = None,
                                user_id: Optional[UUID] = None,
                                requesting_user_role: UserRole = None) -> Dict[str, Any]:
        """Get predictive analytics for future performance."""
        try:
            predictions = {
                "next_month_forecast": {},
                "success_probability": {},
                "recommended_actions": [],
                "confidence_level": "medium"
            }

            # Simple trend-based prediction (in a real system, you'd use ML models)
            win_rate_trends = self.repository.get_win_rate_trends(db, team_id, user_id, days=30)
            
            if len(win_rate_trends) >= 10:
                recent_rates = [t['win_rate'] for t in win_rate_trends[-10:]]
                avg_rate = sum(recent_rates) / len(recent_rates)
                
                # Simple linear trend
                if len(recent_rates) >= 5:
                    early_avg = sum(recent_rates[:5]) / 5
                    late_avg = sum(recent_rates[-5:]) / 5
                    trend = late_avg - early_avg
                    
                    predicted_rate = avg_rate + trend
                    predictions["next_month_forecast"]["win_rate"] = max(0, min(100, predicted_rate))

            # Get current performance
            current_kpis = self.repository.get_dashboard_kpis(db, "team" if team_id else "admin", team_id, user_id)
            
            if current_kpis:
                current_win_rate = float(current_kpis.get('win_rate', 0))
                
                if current_win_rate > 20:
                    predictions["success_probability"]["high_performance"] = 0.8
                elif current_win_rate > 10:
                    predictions["success_probability"]["high_performance"] = 0.6
                else:
                    predictions["success_probability"]["high_performance"] = 0.3

            # Generate recommendations based on patterns
            if predictions["next_month_forecast"].get("win_rate", 0) < current_kpis.get('win_rate', 0):
                predictions["recommended_actions"].append({
                    "action": "Increase bid quality focus - declining trend detected",
                    "impact_score": 8.5
                })

            return predictions

        except Exception as e:
            logger.error(f"Error getting predictive analytics: {e}")
            return {}

    def get_competitive_analysis(self, db: Session, vertical_id: Optional[UUID] = None,
                                requesting_user_role: UserRole = None) -> Dict[str, Any]:
        """Get competitive analysis data."""
        try:
            # This would typically integrate with external market data
            # For now, return internal vertical performance comparison
            vertical_breakdown = self.repository.get_vertical_breakdown(db)
            
            analysis = {
                "market_position": "competitive",
                "vertical_performance": vertical_breakdown,
                "opportunities": [],
                "threats": []
            }

            # Analyze vertical performance
            if vertical_breakdown:
                avg_win_rate = sum(v['win_rate'] for v in vertical_breakdown) / len(vertical_breakdown)
                
                for vertical in vertical_breakdown:
                    if vertical['win_rate'] > avg_win_rate * 1.2:
                        analysis["opportunities"].append({
                            "vertical": vertical['name'],
                            "reason": "Above average win rate",
                            "recommendation": "Increase focus and resources"
                        })
                    elif vertical['win_rate'] < avg_win_rate * 0.8:
                        analysis["threats"].append({
                            "vertical": vertical['name'],
                            "reason": "Below average win rate",
                            "recommendation": "Review strategy or consider exit"
                        })

            return analysis

        except Exception as e:
            logger.error(f"Error getting competitive analysis: {e}")
            return {}

    def cache_analytics_results(self, key: str, data: Dict[str, Any], ttl_minutes: int = 15) -> None:
        """Cache analytics results for performance."""
        try:
            self.repository.cache_analytics_data(key, data, ttl_minutes)
        except Exception as e:
            logger.error(f"Error caching analytics results: {e}")

    def get_cached_analytics(self, key: str) -> Optional[Dict[str, Any]]:
        """Get cached analytics data."""
        try:
            return self.repository.get_cached_analytics_data(key)
        except Exception as e:
            logger.error(f"Error getting cached analytics: {e}")
            return None

    def generate_analytics_cache_key(self, scope: str, params: Dict[str, Any]) -> str:
        """Generate cache key for analytics data."""
        try:
            # Create a deterministic key from parameters
            sorted_params = sorted(params.items())
            key_string = f"analytics:{scope}:{hash(str(sorted_params))}"
            return hashlib.md5(key_string.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            return f"analytics:{scope}:default"

    # Private helper methods

    def _apply_role_filters(self, requesting_user_role: UserRole,
                           requesting_user_team_id: Optional[UUID],
                           requesting_user_id: Optional[UUID],
                           requested_team_id: Optional[UUID],
                           requested_user_id: Optional[UUID]) -> tuple[Optional[UUID], Optional[UUID]]:
        """Apply role-based filtering to requested IDs."""
        filtered_team_id = requested_team_id
        filtered_user_id = requested_user_id

        if requesting_user_role == UserRole.SUB_ADMIN:
            # Sub-admin can only see their team's data
            if filtered_team_id and filtered_team_id != requesting_user_team_id:
                filtered_team_id = requesting_user_team_id
            elif not filtered_team_id:
                filtered_team_id = requesting_user_team_id

        elif requesting_user_role == UserRole.MEMBER:
            # Member can only see their own data
            filtered_team_id = requesting_user_team_id
            filtered_user_id = requesting_user_id

        return filtered_team_id, filtered_user_id

    def _calculate_date_range(self, range_type: str, from_date: Optional[datetime],
                             to_date: Optional[datetime]) -> tuple[date, date]:
        """Calculate date range based on range type."""
        today = date.today()

        if range_type == "custom" and from_date and to_date:
            return from_date.date(), to_date.date()
        elif range_type == "day":
            return today, today
        elif range_type == "week":
            start_date = today - timedelta(days=today.weekday())
            end_date = start_date + timedelta(days=6)
            return start_date, end_date
        elif range_type == "month":
            start_date = today.replace(day=1)
            if today.month == 12:
                end_date = date(today.year + 1, 1, 1) - timedelta(days=1)
            else:
                end_date = date(today.year, today.month + 1, 1) - timedelta(days=1)
            return start_date, end_date
        else:
            # Default to last 30 days
            return today - timedelta(days=30), today

    def _export_to_csv(self, data: Dict[str, Any]) -> str:
        """Export data to CSV format."""
        output = io.StringIO()
        
        # Handle different data structures
        if 'summary' in data and isinstance(data['summary'], dict):
            writer = csv.writer(output)
            writer.writerow(['Metric', 'Value'])
            for key, value in data['summary'].items():
                writer.writerow([key, value])
        
        return output.getvalue()

    def _export_to_xlsx(self, data: Dict[str, Any]) -> bytes:
        """Export data to Excel format."""
        output = io.BytesIO()
        
        # Convert to DataFrame and export
        if 'summary' in data:
            df = pd.DataFrame([data['summary']])
            df.to_excel(output, index=False, engine='openpyxl')
        
        output.seek(0)
        return output.getvalue()

    def _export_to_pdf(self, data: Dict[str, Any]) -> bytes:
        """Export data to PDF format."""
        # This would require a PDF library like ReportLab
        # For now, return a placeholder
        return b"PDF export not implemented yet"