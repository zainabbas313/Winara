# services/analytics_service.py
import os
from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session
import hashlib
import json
import logging
import io
import csv
import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import inch

from interface.Iservices.analytics_service import IAnalyticsService
from interface.Irepositories.analytics_repository import IAnalyticsRepository
from repositories.analytics_repository import AnalyticsRepository
from schemas.analytics import (
    AnalyticsScope, DashboardAnalytics, ReportRequest, ReportResponse,
    BidPerformanceReport, FinancialReport, OperationalReport,
    KPIData, ChartDataPoint, VerticalBreakdown, TeamPerformance, MemberPerformance,
    FinancialSummary, CostSummary, ProfitSummary, ProductivityMetrics, 
    EfficiencyMetrics, QualityMetrics, PerformanceInsights, PredictiveAnalytics,
    Insight, Recommendation, InsightType
)
from schemas.common import ExportRequest, ExportResponse
from models.models import UserRole
from utils.exceptions import AnalyticsError, ValidationError, PermissionError as CustomPermissionError

logger = logging.getLogger(__name__)


class AnalyticsService(IAnalyticsService):
    def __init__(self):
        self.repository: IAnalyticsRepository = AnalyticsRepository()

    def get_dashboard_analytics(self, db: Session, scope_data: AnalyticsScope,
                               requesting_user_id: UUID, requesting_user_role: UserRole,
                               requesting_user_team_id: Optional[UUID] = None) -> DashboardAnalytics:
        """Get dashboard analytics with comprehensive validation and caching."""
        try:
            logger.info(f"Getting dashboard analytics with scope: {scope_data.scope}")
        
            # If calling receivables internally, add validation
            if scope_data.team_id:
                logger.info(f"Team ID being passed: {scope_data.team_id}")
                # Ensure it's a valid UUID before passing to receivables
                if not isinstance(scope_data.team_id, UUID):
                    raise ValueError(f"Team ID must be UUID, got: {type(scope_data.team_id)}")
                    
            # Validate access permissions
            self._validate_analytics_access(
                scope_data.scope, requesting_user_role,
                scope_data.team_id, scope_data.user_id,
                requesting_user_team_id, requesting_user_id
            )

            # Generate cache key
            cache_key = self._generate_analytics_cache_key("dashboard", {
                "scope": scope_data.scope,
                "team_id": str(scope_data.team_id) if scope_data.team_id else None,
                "user_id": str(scope_data.user_id) if scope_data.user_id else None,
                "range": scope_data.range,
                "from_date": scope_data.from_date.isoformat() if scope_data.from_date else None,
                "to_date": scope_data.to_date.isoformat() if scope_data.to_date else None
            })

            # Check cache first
            cached_data = self.repository.get_cached_analytics_data(cache_key)
            if cached_data:
                logger.info(f"Returning cached dashboard analytics for scope: {scope_data.scope}")
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

            # Get KPIs with enhanced error handling
            kpi_data = self.repository.get_dashboard_kpis(
                db, scope_data.scope, filtered_team_id, filtered_user_id,
                date_from, date_to
            )

            if not kpi_data:
                logger.warning(f"No KPI data found for scope: {scope_data.scope}")
                kpi_data = self._get_empty_kpis()

            # Get chart data
            charts_data = self._get_dashboard_charts(
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

            result = DashboardAnalytics(
                kpis=kpis,
                charts=charts_data,
                generated_at=datetime.utcnow(),
                scope=scope_data.scope
            )

            # Cache the result
            self.repository.cache_analytics_data(cache_key, result.dict(), ttl_minutes=15)
            
            logger.info(f"Successfully generated dashboard analytics for scope: {scope_data.scope}")
            return result

        except CustomPermissionError as e:
            logger.error(f"Permission denied for dashboard analytics: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting dashboard analytics: {e}")
            raise AnalyticsError(f"Failed to generate dashboard analytics: {str(e)}")

    def generate_report(self, db: Session, report_request: ReportRequest,
                       requesting_user_id: UUID, requesting_user_role: UserRole,
                       requesting_user_team_id: Optional[UUID] = None) -> ReportResponse:
        """Generate comprehensive analytics report."""
        try:
            # Validate report request
            self._validate_report_request(report_request)

            # Extract and validate filters
            filters = report_request.filters or {}
            team_id = UUID(filters.get('team_id')) if filters.get('team_id') else None
            user_id = UUID(filters.get('user_id')) if filters.get('user_id') else None
            date_from = self._parse_date(filters.get('date_from'))
            date_to = self._parse_date(filters.get('date_to'))

            # Apply role-based filtering
            filtered_team_id, filtered_user_id = self._apply_role_filters(
                requesting_user_role, requesting_user_team_id, requesting_user_id,
                team_id, user_id
            )

            # Generate appropriate report based on type
            data = self._generate_report_data(
                db, report_request.type, filtered_team_id, filtered_user_id, 
                date_from, date_to, requesting_user_role, requesting_user_team_id
            )

            record_count = self._calculate_record_count(data, report_request.type)

            logger.info(f"Successfully generated {report_request.type} report with {record_count} records")

            return ReportResponse(
                type=report_request.type,
                generated_at=datetime.utcnow(),
                data=data,
                filters_applied=filters,
                record_count=record_count
            )

        except ValidationError as e:
            logger.error(f"Validation error in report generation: {e}")
            raise
        except Exception as e:
            logger.error(f"Error generating report: {e}")
            raise AnalyticsError(f"Failed to generate {report_request.type} report: {str(e)}")

    def export_analytics(self, db: Session, export_request: ExportRequest,
                        requesting_user_id: UUID, requesting_user_role: UserRole,
                        requesting_user_team_id: Optional[UUID] = None) -> ExportResponse:
        """Export analytics data in various formats with enhanced functionality."""
        try:
            # Generate report data first
            report_request = ReportRequest(
                type=export_request.type,
                filters=export_request.filters
            )
            
            report_response = self.generate_report(
                db, report_request, requesting_user_id, 
                requesting_user_role, requesting_user_team_id
            )

            # Export in requested format
            file_content, content_type = self._export_data(
                report_response.data, export_request.format, export_request.include_charts
            )

            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{export_request.type}_{timestamp}.{export_request.format.value}"

            # Calculate file size
            file_size = len(file_content) if isinstance(file_content, bytes) else len(file_content.encode())

            logger.info(f"Successfully exported {export_request.type} as {export_request.format}")

            export_dir = "exports"
            os.makedirs(export_dir, exist_ok=True)
            file_path = os.path.join(export_dir, filename)

            with open(file_path, "wb") as f:
                f.write(file_content if isinstance(file_content, bytes) else file_content.encode())

            return ExportResponse(
                filename=filename,
                content_type=content_type,
                file_size=file_size,
                download_url=f"/analytics/{filename}",
                expires_at=datetime.utcnow() + timedelta(hours=24),
                generated_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error exporting analytics: {e}")
            raise AnalyticsError(f"Failed to export analytics: {str(e)}")

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

            if not report_data:
                logger.warning("No bid performance data found")
                report_data = self._get_empty_bid_performance_data()

            # Transform to schema format
            summary = KPIData(**report_data['summary'])
            
            team_breakdown = [
                TeamPerformance(**team) for team in report_data.get('team_breakdown', [])
            ]
            
            member_breakdown = [
                MemberPerformance(**member) for member in report_data.get('member_breakdown', [])
            ]
            
            vertical_breakdown = [
                VerticalBreakdown(**vertical) for vertical in report_data.get('vertical_breakdown', [])
            ]
            
            trends = [
                ChartDataPoint(
                    date=trend['date'],
                    bids=trend.get('bids'),
                    wins=trend.get('wins'),
                    win_rate=trend.get('win_rate')
                )
                for trend in report_data.get('trends', [])
            ]

            return BidPerformanceReport(
                summary=summary,
                team_breakdown=team_breakdown,
                member_breakdown=member_breakdown,
                vertical_breakdown=vertical_breakdown,
                trends=trends,
                generated_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error generating bid performance report: {e}")
            raise AnalyticsError(f"Failed to generate bid performance report: {str(e)}")

    def get_financial_report(self, db: Session, team_id: Optional[UUID] = None,
                            date_from: Optional[date] = None, date_to: Optional[date] = None,
                            requesting_user_role: UserRole = None,
                            requesting_user_team_id: Optional[UUID] = None) -> FinancialReport:
        """Generate comprehensive financial report."""
        try:
            # Apply role-based filtering
            filtered_team_id, _ = self._apply_role_filters(
                requesting_user_role, requesting_user_team_id, None, team_id, None
            )

            # Get report data from repository
            report_data = self.repository.get_financial_report(
                db, filtered_team_id, date_from, date_to
            )

            if not report_data:
                logger.warning("No financial data found")
                report_data = self._get_empty_financial_data()

            # Transform to schema format
            revenue_summary = FinancialSummary(**report_data['revenue_summary'])
            cost_summary = CostSummary(**report_data['cost_summary'])
            profit_summary = ProfitSummary(**report_data['profit_summary'])

            monthly_trends = [
                ChartDataPoint(
                    date=trend['date'],
                    revenue=Decimal(str(trend.get('expected_revenue', 0))),
                    actual_revenue=Decimal(str(trend.get('actual_revenue', 0)))
                )
                for trend in report_data.get('monthly_trends', [])
            ]

            return FinancialReport(
                revenue_summary=revenue_summary,
                cost_summary=cost_summary,
                profit_summary=profit_summary,
                receivables_summary=report_data.get('receivables_aging', {}),
                monthly_trends=monthly_trends,
                generated_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error generating financial report: {e}")
            raise AnalyticsError(f"Failed to generate financial report: {str(e)}")

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

            if not report_data:
                logger.warning("No operational data found")
                report_data = self._get_empty_operational_data()

            # Transform to schema format
            productivity_metrics = ProductivityMetrics(**report_data['productivity_metrics'])
            efficiency_metrics = EfficiencyMetrics(**report_data['efficiency_metrics'])
            quality_metrics = QualityMetrics(**report_data['quality_metrics'])

            team_utilization = [
                TeamPerformance(**team) for team in report_data.get('team_utilization', [])
            ]

            return OperationalReport(
                productivity_metrics=productivity_metrics,
                efficiency_metrics=efficiency_metrics,
                quality_metrics=quality_metrics,
                team_utilization=team_utilization,
                generated_at=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Error generating operational report: {e}")
            raise AnalyticsError(f"Failed to generate operational report: {str(e)}")

    def get_performance_insights(self, db: Session, team_id: Optional[UUID] = None,
                                user_id: Optional[UUID] = None,
                                requesting_user_role: UserRole = None) -> Dict[str, Any]:
        """Get AI-powered performance insights and recommendations."""
        try:
            insights = []
            recommendations = []

            # Get win rate trends for analysis
            win_rate_trends = self.repository.get_win_rate_trends(db, team_id, user_id, days=30)
            
            if len(win_rate_trends) >= 7:
                # Analyze recent trends
                recent_rates = [t['win_rate'] for t in win_rate_trends[-7:]]
                older_rates = [t['win_rate'] for t in win_rate_trends[-14:-7]] if len(win_rate_trends) >= 14 else recent_rates
                
                recent_avg = sum(recent_rates) / len(recent_rates)
                older_avg = sum(older_rates) / len(older_rates)
                
                if recent_avg > older_avg * 1.15:  # 15% improvement
                    insights.append(Insight(
                        type=InsightType.POSITIVE_TREND,
                        message=f"Win rate has improved by {((recent_avg / older_avg - 1) * 100):.1f}% in the last week",
                        impact="high",
                        confidence=0.8,
                        suggested_actions=["Continue current strategy", "Document successful approaches"]
                    ))
                elif recent_avg < older_avg * 0.85:  # 15% decline
                    insights.append(Insight(
                        type=InsightType.NEGATIVE_TREND,
                        message=f"Win rate has declined by {((1 - recent_avg / older_avg) * 100):.1f}% in the last week",
                        impact="high",
                        confidence=0.8,
                        suggested_actions=["Review bid quality", "Analyze competitor activity"]
                    ))
                    recommendations.append(Recommendation(
                        action="Review recent bid quality and targeting strategy",
                        priority="high",
                        impact_score=8.5,
                        estimated_effort="medium"
                    ))

            # Analyze cost efficiency
            cost_analysis = self.repository.get_cost_analysis(db, team_id, user_id)
            cost_per_win = cost_analysis.get('cost_per_win', 0)
            
            if cost_per_win > 50:  # Configurable threshold
                insights.append(Insight(
                    type=InsightType.ALERT,
                    message=f"Cost per win (${cost_per_win:.2f}) is above optimal threshold",
                    impact="medium",
                    confidence=0.7,
                    suggested_actions=["Optimize connect usage", "Focus on higher-probability bids"]
                ))
                recommendations.append(Recommendation(
                    action="Consider optimizing connect usage - cost per win is high",
                    priority="medium",
                    impact_score=6.0,
                    estimated_effort="low"
                ))

            # ROI analysis
            roi_analysis = self.repository.get_roi_analysis(db, team_id, user_id)
            roi_percentage = roi_analysis.get('roi_percentage', 0)
            
            if roi_percentage < 100:  # Less than 100% ROI
                insights.append(Insight(
                    type=InsightType.OPPORTUNITY,
                    message=f"Current ROI of {roi_percentage:.1f}% indicates room for improvement",
                    impact="high",
                    confidence=0.9,
                    suggested_actions=["Target higher-value projects", "Improve bid quality"]
                ))
                recommendations.append(Recommendation(
                    action="Focus on higher-value projects to improve ROI",
                    priority="high",
                    impact_score=9.0,
                    estimated_effort="medium"
                ))

            # Benchmark comparisons
            benchmarks = {
                "industry_avg_win_rate": 15.0,
                "cost_per_win_benchmark": 30.0,
                "roi_benchmark": 200.0,
                "response_time_benchmark": 2.0
            }

            # Get current performance metrics
            current_kpis = self.repository.get_dashboard_kpis(
                db, "team" if team_id else "admin", team_id, user_id
            )

            trends = {
                "win_rate_trends": win_rate_trends,
                "cost_trends": cost_analysis,
                "roi_trends": roi_analysis,
                "performance_score": self._calculate_performance_score(current_kpis, benchmarks)
            }

            return PerformanceInsights(
                key_insights=insights,
                recommendations=recommendations,
                benchmarks=benchmarks,
                trends=trends,
                generated_at=datetime.utcnow()
            ).dict()

        except Exception as e:
            logger.error(f"Error getting performance insights: {e}")
            return {"error": "Failed to generate performance insights"}

    def get_predictive_analytics(self, db: Session, team_id: Optional[UUID] = None,
                                user_id: Optional[UUID] = None,
                                requesting_user_role: UserRole = None) -> Dict[str, Any]:
        """Get predictive analytics for future performance."""
        try:
            # Get historical data for prediction
            win_rate_trends = self.repository.get_win_rate_trends(db, team_id, user_id, days=60)
            
            predictions = {}
            recommendations = []
            confidence_level = "medium"
            
            if len(win_rate_trends) >= 20:  # Need sufficient data for prediction
                # Simple trend-based prediction (in production, use ML models)
                recent_rates = [t['win_rate'] for t in win_rate_trends[-20:]]
                
                # Calculate trend using linear regression approximation
                x_values = list(range(len(recent_rates)))
                trend_slope = self._calculate_linear_trend(x_values, recent_rates)
                current_avg = sum(recent_rates[-5:]) / 5
                
                # Predict next month's performance
                predicted_win_rate = max(0, min(100, current_avg + (trend_slope * 30)))
                predictions["win_rate"] = predicted_win_rate
                
                # Estimate bid volume based on historical patterns
                recent_bid_counts = [t['total_bids'] for t in win_rate_trends[-10:]]
                avg_bids_per_day = sum(recent_bid_counts) / len(recent_bid_counts)
                predictions["estimated_monthly_bids"] = int(avg_bids_per_day * 30)
                
                # Revenue prediction
                if predicted_win_rate > 0:
                    roi_data = self.repository.get_roi_analysis(db, team_id, user_id)
                    avg_revenue_per_win = roi_data.get('revenue_per_bid', 0) * (predicted_win_rate / 100)
                    predictions["estimated_monthly_revenue"] = avg_revenue_per_win * predictions["estimated_monthly_bids"]
                
                # Adjust confidence based on trend stability
                rate_variance = self._calculate_variance(recent_rates)
                if rate_variance < 5:  # Low variance
                    confidence_level = "high"
                elif rate_variance > 15:  # High variance
                    confidence_level = "low"

            # Success probability analysis
            current_kpis = self.repository.get_dashboard_kpis(db, "team" if team_id else "admin", team_id, user_id)
            current_win_rate = float(current_kpis.get('win_rate', 0))
            
            success_probability = {}
            if current_win_rate > 25:
                success_probability["high_performance_next_month"] = 0.85
            elif current_win_rate > 15:
                success_probability["high_performance_next_month"] = 0.65
            elif current_win_rate > 10:
                success_probability["high_performance_next_month"] = 0.45
            else:
                success_probability["high_performance_next_month"] = 0.25

            # Generate actionable recommendations
            if predictions.get("win_rate", 0) < current_win_rate:
                recommendations.append(Recommendation(
                    action="Increase bid quality focus - declining trend predicted",
                    priority="high",
                    impact_score=8.5,
                    estimated_effort="medium"
                ))
                
            if predictions.get("estimated_monthly_revenue", 0) < current_kpis.get('revenue', 0):
                recommendations.append(Recommendation(
                    action="Focus on higher-value opportunities to maintain revenue growth",
                    priority="medium",
                    impact_score=7.0,
                    estimated_effort="medium"
                ))

            # Model accuracy estimation (simplified)
            model_accuracy = 0.75 if confidence_level == "high" else 0.60 if confidence_level == "medium" else 0.45

            return PredictiveAnalytics(
                next_month_forecast=predictions,
                success_probability=success_probability,
                recommended_actions=recommendations,
                confidence_level=confidence_level,
                model_accuracy=model_accuracy,
                generated_at=datetime.utcnow()
            ).dict()

        except Exception as e:
            logger.error(f"Error getting predictive analytics: {e}")
            return {"error": "Failed to generate predictive analytics"}

    # Private helper methods

    def _validate_analytics_access(self, scope: str, requesting_user_role: UserRole,
                                 requested_team_id: Optional[UUID] = None,
                                 requested_user_id: Optional[UUID] = None,
                                 requesting_user_team_id: Optional[UUID] = None,
                                 requesting_user_id: Optional[UUID] = None) -> None:
        """Validate analytics access permissions."""
        if requesting_user_role == UserRole.ADMIN:
            return  # Admin has access to everything

        if scope == "admin":
            if requesting_user_role != UserRole.ADMIN:
                raise CustomPermissionError("Admin access required for admin scope")

        elif scope == "team":
            if requesting_user_role == UserRole.SUB_ADMIN:
                if requested_team_id and requested_team_id != requesting_user_team_id:
                    raise CustomPermissionError("Sub-admin can only access their own team data")
            elif requesting_user_role == UserRole.MEMBER:
                raise CustomPermissionError("Members cannot access team scope")

        elif scope == "member":
            if requesting_user_role == UserRole.MEMBER:
                if requested_user_id and requested_user_id != requesting_user_id:
                    raise CustomPermissionError("Members can only access their own data")
            elif requesting_user_role == UserRole.SUB_ADMIN:
                # Additional validation would be needed to ensure user is in same team
                pass

    def _validate_report_request(self, report_request: ReportRequest) -> None:
        """Validate report request parameters."""
        if not report_request.type:
            raise ValidationError("Report type is required")
        
        if report_request.filters:
            date_from = report_request.filters.get('date_from')
            date_to = report_request.filters.get('date_to')
            
            if date_from and date_to:
                from_date = self._parse_date(date_from)
                to_date = self._parse_date(date_to)
                
                if from_date and to_date and from_date > to_date:
                    raise ValidationError("date_from cannot be after date_to")

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
            if filtered_team_id != requesting_user_team_id:
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

    def _get_dashboard_charts(self, db: Session, team_id: Optional[UUID],
                             user_id: Optional[UUID], date_from: date, date_to: date) -> Dict[str, List[Any]]:
        """Get all chart data for dashboard."""
        try:
            bids_over_time = self.repository.get_bids_over_time(
                db, team_id, user_id, date_from, date_to
            )
            
            revenue_over_time = self.repository.get_revenue_over_time(
                db, team_id, user_id, date_from, date_to
            )
            
            vertical_breakdown = self.repository.get_vertical_breakdown(
                db, team_id, user_id, date_from, date_to
            )
            
            return {
                'bids_over_time': bids_over_time,
                'revenue_over_time': revenue_over_time,
                'vertical_breakdown': vertical_breakdown
            }
        except Exception as e:
            logger.error(f"Error getting dashboard charts: {e}")
            return {}

    def _generate_report_data(self, db: Session, report_type: str,
                             team_id: Optional[UUID], user_id: Optional[UUID],
                             date_from: Optional[date], date_to: Optional[date],
                             requesting_user_role: UserRole,
                             requesting_user_team_id: Optional[UUID]) -> Dict[str, Any]:
        """Generate report data based on type."""
        if report_type == "bid_performance":
            return self.repository.get_bid_performance_report(db, team_id, date_from, date_to)
        elif report_type == "financial":
            return self.repository.get_financial_report(db, team_id, date_from, date_to)
        elif report_type == "operational":
            return self.repository.get_operational_report(db, team_id, date_from, date_to)
        else:
            raise ValidationError(f"Invalid report type: {report_type}")

    def _export_data(self, data: Dict[str, Any], format_type: str, include_charts: bool = False) -> tuple[Any, str]:
        """Export data in specified format."""
        if format_type == "csv":
            return self._export_to_csv(data), "text/csv"
        elif format_type == "xlsx":
            return self._export_to_xlsx(data), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif format_type == "pdf":
            return self._export_to_pdf(data, include_charts), "application/pdf"
        elif format_type == "json":
            return json.dumps(data, indent=2, default=str), "application/json"
        else:
            raise ValidationError(f"Unsupported export format: {format_type}")

    def _export_to_csv(self, data: Dict[str, Any]) -> str:
        """Export data to CSV format."""
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Export summary data
        if 'summary' in data and isinstance(data['summary'], dict):
            writer.writerow(['Summary Metrics'])
            writer.writerow(['Metric', 'Value'])
            for key, value in data['summary'].items():
                writer.writerow([key.replace('_', ' ').title(), value])
            writer.writerow([])  # Empty row
        
        # Export breakdown data
        for section, section_data in data.items():
            if section != 'summary' and isinstance(section_data, list) and section_data:
                writer.writerow([section.replace('_', ' ').title()])
                
                if section_data:
                    # Write headers
                    headers = list(section_data[0].keys())
                    writer.writerow(headers)
                    
                    # Write data rows
                    for row in section_data:
                        writer.writerow([row.get(header, '') for header in headers])
                    
                writer.writerow([])  # Empty row
        
        return output.getvalue()

    def _export_to_xlsx(self, data: Dict[str, Any]) -> bytes:
        """Export data to Excel format."""
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Export summary data
            if 'summary' in data and isinstance(data['summary'], dict):
                summary_df = pd.DataFrame(list(data['summary'].items()), 
                                        columns=['Metric', 'Value'])
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Export breakdown data
            for section, section_data in data.items():
                if section != 'summary' and isinstance(section_data, list) and section_data:
                    df = pd.DataFrame(section_data)
                    sheet_name = section.replace('_', ' ').title()[:31]  # Excel sheet name limit
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        output.seek(0)
        return output.getvalue()

    def _export_to_pdf(self, data: Dict[str, Any], include_charts: bool = False) -> bytes:
        """Export data to PDF format."""
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer, pagesize=letter)
        width, height = letter
        
        # Title
        p.setFont("Helvetica-Bold", 16)
        p.drawString(50, height - 50, "Analytics Report")
        
        y_position = height - 100
        
        # Summary section
        if 'summary' in data and isinstance(data['summary'], dict):
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, y_position, "Summary")
            y_position -= 30
            
            p.setFont("Helvetica", 10)
            for key, value in data['summary'].items():
                p.drawString(70, y_position, f"{key.replace('_', ' ').title()}: {value}")
                y_position -= 15
                
                if y_position < 50:  # New page
                    p.showPage()
                    y_position = height - 50
            
            y_position -= 20
        
        # Add other sections
        for section, section_data in data.items():
            if section != 'summary' and isinstance(section_data, list) and section_data:
                if y_position < 200:  # Need new page
                    p.showPage()
                    y_position = height - 50
                
                p.setFont("Helvetica-Bold", 12)
                p.drawString(50, y_position, section.replace('_', ' ').title())
                y_position -= 20
                
                # Show first few items
                p.setFont("Helvetica", 9)
                for i, item in enumerate(section_data[:10]):  # Limit to first 10 items
                    if isinstance(item, dict):
                        item_text = ", ".join([f"{k}: {v}" for k, v in list(item.items())[:3]])
                        p.drawString(70, y_position, item_text[:80] + "..." if len(item_text) > 80 else item_text)
                        y_position -= 12
                        
                        if y_position < 50:
                            break
                
                if len(section_data) > 10:
                    p.drawString(70, y_position, f"... and {len(section_data) - 10} more items")
                    y_position -= 15
                
                y_position -= 20
        
        p.save()
        buffer.seek(0)
        return buffer.getvalue()

    def _calculate_record_count(self, data: Dict[str, Any], report_type: str) -> int:
        """Calculate total record count in report."""
        count = 0
        for key, value in data.items():
            if isinstance(value, list):
                count += len(value)
        return count

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string to date object."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except (ValueError, AttributeError):
            return None

    def _generate_analytics_cache_key(self, scope: str, params: Dict[str, Any]) -> str:
        """Generate cache key for analytics data."""
        try:
            # Create a deterministic key from parameters
            sorted_params = sorted(params.items())
            key_string = f"analytics:{scope}:{hash(str(sorted_params))}"
            return hashlib.md5(key_string.encode()).hexdigest()
        except Exception as e:
            logger.error(f"Error generating cache key: {e}")
            return f"analytics:{scope}:default"

    def _calculate_linear_trend(self, x_values: List[int], y_values: List[float]) -> float:
        """Calculate linear trend slope."""
        if len(x_values) != len(y_values) or len(x_values) < 2:
            return 0.0
        
        n = len(x_values)
        x_mean = sum(x_values) / n
        y_mean = sum(y_values) / n
        
        numerator = sum((x_values[i] - x_mean) * (y_values[i] - y_mean) for i in range(n))
        denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
        
        return numerator / denominator if denominator != 0 else 0.0

    def _calculate_variance(self, values: List[float]) -> float:
        """Calculate variance of values."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        return sum((x - mean) ** 2 for x in values) / len(values)

    def _calculate_performance_score(self, kpis: Dict[str, Any], benchmarks: Dict[str, float]) -> float:
        """Calculate overall performance score."""
        try:
            win_rate = float(kpis.get('win_rate', 0))
            roi = float(kpis.get('profit_margin', 0))
            
            # Normalize against benchmarks
            win_rate_score = min(100, (win_rate / benchmarks['industry_avg_win_rate']) * 100)
            roi_score = min(100, (roi / benchmarks['roi_benchmark']) * 100)
            
            # Weighted average
            return (win_rate_score * 0.6) + (roi_score * 0.4)
        except Exception:
            return 0.0

    def _get_empty_kpis(self) -> Dict[str, Any]:
        """Return empty KPIs structure."""
        return {
            'total_bids': 0,
            'wins': 0,
            'win_rate': Decimal('0'),
            'connect_spend': Decimal('0'),
            'revenue': Decimal('0'),
            'profit_margin': Decimal('0')
        }

    def _get_empty_bid_performance_data(self) -> Dict[str, Any]:
        """Return empty bid performance data structure."""
        return {
            'summary': self._get_empty_kpis(),
            'team_breakdown': [],
            'member_breakdown': [],
            'vertical_breakdown': [],
            'trends': []
        }

    def _get_empty_financial_data(self) -> Dict[str, Any]:
        """Return empty financial data structure."""
        return {
            'revenue_summary': {
                'total_expected': 0,
                'total_received': 0,
                'pending_count': 0,
                'pending_value': 0,
                'overdue_count': 0,
                'overdue_value': 0
            },
            'cost_summary': {
                'total_connects_cost': 0,
                'total_connects_used': 0,
                'avg_cost_per_bid': 0,
                'cost_per_win': 0
            },
            'profit_summary': {
                'gross_profit': 0,
                'profit_margin': 0,
                'net_profit': 0,
                'roi_percentage': 0
            },
            'monthly_trends': []
        }

    def _get_empty_operational_data(self) -> Dict[str, Any]:
        """Return empty operational data structure."""
        return {
            'productivity_metrics': {
                'total_teams': 0,
                'total_members': 0,
                'active_members': 0,
                'bids_per_day': 0,
                'bids_per_member': 0
            },
            'efficiency_metrics': {
                'avg_response_time_days': 0,
                'win_rate': 0,
                'decline_rate': 0,
                'conversion_rate': 0
            },
            'quality_metrics': {
                'total_bids': 0,
                'wins': 0,
                'declined': 0,
                'quality_score': 0
            },
            'team_utilization': []
        }