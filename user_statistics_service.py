"""
用户统计服务：匿名用户留存率统计
无需注册，使用设备ID追踪用户
"""
import logging
from datetime import datetime, date, timedelta
from models_v2 import db, UserSession, DailyActiveUser
from sqlalchemy import func, distinct
from sqlalchemy.sql import and_

logger = logging.getLogger(__name__)


class UserStatisticsService:
    """用户统计服务类"""
    
    def __init__(self):
        pass
    
    def get_or_create_device_id(self, device_id=None):
        """
        获取或生成设备ID
        
        Args:
            device_id: 客户端提供的设备ID（可选）
            
        Returns:
            str: 设备ID
        """
        if device_id and device_id.strip():
            return device_id.strip()
        
        # 如果没有提供，生成一个UUID作为设备ID
        import uuid
        return str(uuid.uuid4())
    
    def track_user_activity(self, device_id, device_info=None, app_version=None, question_count=0):
        """
        追踪用户活动（自动记录到数据库）
        
        Args:
            device_id: 设备ID
            device_info: 设备信息字典（可选）
            app_version: 应用版本号（可选）
            question_count: 本次会话的题目数（默认0）
        """
        try:
            today = date.today()
            
            # 获取或创建用户会话
            user_session = UserSession.query.filter_by(device_id=device_id).first()
            
            if user_session:
                # 更新现有会话
                user_session.last_active_date = today
                user_session.total_sessions += 1
                user_session.total_questions += question_count
                if device_info:
                    user_session.device_info = device_info
                if app_version:
                    user_session.app_version = app_version
                user_session.updated_at = datetime.utcnow()
            else:
                # 创建新会话
                user_session = UserSession(
                    device_id=device_id,
                    first_seen_date=today,
                    last_active_date=today,
                    total_sessions=1,
                    total_questions=question_count,
                    device_info=device_info,
                    app_version=app_version
                )
                db.session.add(user_session)
            
            # 记录每日活跃用户
            daily_active = DailyActiveUser.query.filter_by(
                device_id=device_id,
                date=today
            ).first()
            
            if daily_active:
                # 更新当日记录
                daily_active.session_count += 1
                daily_active.question_count += question_count
            else:
                # 创建当日记录
                daily_active = DailyActiveUser(
                    device_id=device_id,
                    date=today,
                    question_count=question_count,
                    session_count=1
                )
                db.session.add(daily_active)
            
            db.session.commit()
            logger.info(f"[UserStats] ✅ 用户活动已记录到数据库: {device_id}, 题目数: {question_count}, 日期: {today}")
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"[UserStats] ❌ 记录用户活动失败: {e}", exc_info=True)
    
    def calculate_retention_rate(self, start_date=None, days=7):
        """
        计算留存率
        
        Args:
            start_date: 起始日期（默认：7天前）
            days: 计算多少天的留存率（默认7天）
            
        Returns:
            dict: 留存率数据
        """
        try:
            if not start_date:
                start_date = date.today() - timedelta(days=days)
            
            # 获取起始日期的新增用户数
            new_users = UserSession.query.filter(
                UserSession.first_seen_date == start_date
            ).count()
            
            if new_users == 0:
                return {
                    'start_date': start_date.isoformat(),
                    'days': days,
                    'new_users': 0,
                    'retention_data': [],
                    'message': '起始日期没有新增用户'
                }
            
            # 计算每日留存率
            retention_data = []
            for day_offset in range(days + 1):
                check_date = start_date + timedelta(days=day_offset)
                
                # 查询在起始日期首次使用，且在检查日期活跃的用户数
                retained_users = db.session.query(
                    distinct(DailyActiveUser.device_id)
                ).join(
                    UserSession,
                    DailyActiveUser.device_id == UserSession.device_id
                ).filter(
                    and_(
                        UserSession.first_seen_date == start_date,
                        DailyActiveUser.date == check_date
                    )
                ).count()
                
                retention_rate = (retained_users / new_users * 100) if new_users > 0 else 0
                
                retention_data.append({
                    'day': day_offset,
                    'date': check_date.isoformat(),
                    'retained_users': retained_users,
                    'retention_rate': round(retention_rate, 2)
                })
            
            return {
                'start_date': start_date.isoformat(),
                'days': days,
                'new_users': new_users,
                'retention_data': retention_data
            }
            
        except Exception as e:
            logger.error(f"[UserStats] 计算留存率失败: {e}", exc_info=True)
            return {
                'error': str(e),
                'start_date': start_date.isoformat() if start_date else None,
                'days': days
            }
    
    def get_user_statistics(self, days=30):
        """
        获取用户统计数据
        
        Args:
            days: 统计最近多少天（默认30天）
            
        Returns:
            dict: 统计数据
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # 总用户数
            total_users = UserSession.query.count()
            
            # 活跃用户数（最近N天）
            active_users = db.session.query(
                distinct(DailyActiveUser.device_id)
            ).filter(
                DailyActiveUser.date >= start_date
            ).count()
            
            # 新增用户数（最近N天）
            new_users = UserSession.query.filter(
                UserSession.first_seen_date >= start_date
            ).count()
            
            # 每日活跃用户数（DAU）
            daily_active_users = db.session.query(
                DailyActiveUser.date,
                func.count(distinct(DailyActiveUser.device_id)).label('count')
            ).filter(
                DailyActiveUser.date >= start_date
            ).group_by(
                DailyActiveUser.date
            ).order_by(
                DailyActiveUser.date.desc()
            ).all()
            
            dau_data = [
                {
                    'date': row.date.isoformat(),
                    'count': row.count
                }
                for row in daily_active_users
            ]
            
            # 平均每日活跃用户数
            avg_dau = sum(d['count'] for d in dau_data) / len(dau_data) if dau_data else 0
            
            return {
                'period': {
                    'start_date': start_date.isoformat(),
                    'end_date': end_date.isoformat(),
                    'days': days
                },
                'total_users': total_users,
                'active_users': active_users,
                'new_users': new_users,
                'avg_dau': round(avg_dau, 2),
                'daily_active_users': dau_data
            }
            
        except Exception as e:
            logger.error(f"[UserStats] 获取统计数据失败: {e}", exc_info=True)
            return {
                'error': str(e)
            }
    
    def get_cohort_retention(self, cohort_days=7, retention_days=30):
        """
        获取 cohort 留存率（按首次使用日期分组）
        
        Args:
            cohort_days: 计算多少天的cohort（默认7天）
            retention_days: 追踪多少天的留存（默认30天）
            
        Returns:
            dict: cohort留存数据
        """
        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=cohort_days)
            
            cohorts = []
            
            # 按日期分组计算cohort
            for day_offset in range(cohort_days):
                cohort_date = start_date + timedelta(days=day_offset)
                
                # 该日期的新增用户数
                new_users = UserSession.query.filter(
                    UserSession.first_seen_date == cohort_date
                ).count()
                
                if new_users == 0:
                    continue
                
                # 计算该cohort的留存率
                retention_data = []
                for retention_day in range(min(retention_days, (end_date - cohort_date).days + 1)):
                    check_date = cohort_date + timedelta(days=retention_day)
                    
                    retained_users = db.session.query(
                        distinct(DailyActiveUser.device_id)
                    ).join(
                        UserSession,
                        DailyActiveUser.device_id == UserSession.device_id
                    ).filter(
                        and_(
                            UserSession.first_seen_date == cohort_date,
                            DailyActiveUser.date == check_date
                        )
                    ).count()
                    
                    retention_rate = (retained_users / new_users * 100) if new_users > 0 else 0
                    
                    retention_data.append({
                        'day': retention_day,
                        'date': check_date.isoformat(),
                        'retained_users': retained_users,
                        'retention_rate': round(retention_rate, 2)
                    })
                
                cohorts.append({
                    'cohort_date': cohort_date.isoformat(),
                    'new_users': new_users,
                    'retention_data': retention_data
                })
            
            return {
                'cohort_days': cohort_days,
                'retention_days': retention_days,
                'cohorts': cohorts
            }
            
        except Exception as e:
            logger.error(f"[UserStats] 计算cohort留存率失败: {e}", exc_info=True)
            return {
                'error': str(e)
            }


# 全局服务实例（单例）
_user_statistics_service = None

def get_user_statistics_service():
    """获取用户统计服务实例（单例模式）"""
    global _user_statistics_service
    if _user_statistics_service is None:
        _user_statistics_service = UserStatisticsService()
    return _user_statistics_service
