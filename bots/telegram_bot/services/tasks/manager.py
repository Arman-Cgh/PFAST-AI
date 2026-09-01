from datetime import datetime

from database.db import get_connection


class TaskManager:

    # ==========================
    # Create
    # ==========================

    @staticmethod
    def create(
        user_id: int,
        title: str,
        description: str = "",
        due_date: str = "",
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO tasks (
                    user_id,
                    title,
                    description,
                    due_date,
                    completed
                )
                VALUES (?, ?, ?, ?, 0)
                """,
                (
                    user_id,
                    title,
                    description,
                    due_date,
                ),
            )

            conn.commit()

            return cursor.lastrowid

        finally:

            conn.close()

    # ==========================
    # Get By ID
    # ==========================

    @staticmethod
    def get_by_id(
        task_id: int,
        user_id: int,
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    due_date,
                    completed
                FROM tasks
                WHERE id = ?
                  AND user_id = ?
                LIMIT 1
                """,
                (
                    task_id,
                    user_id,
                ),
            )

            row = cursor.fetchone()

            if not row:
                return None

            return {
                "id": row[0],
                "title": row[1],
                "description": row[2],
                "due_date": row[3],
                "completed": bool(row[4]),
            }

        finally:

            conn.close()

    # ==========================
    # Pending
    # ==========================

    @staticmethod
    def get_pending(
        user_id: int,
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    due_date
                FROM tasks
                WHERE user_id = ?
                  AND completed = 0
                ORDER BY id DESC
                """,
                (user_id,),
            )

            rows = cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "due_date": row[3],
                }
                for row in rows
            ]

        finally:

            conn.close()

    # ==========================
    # All
    # ==========================

    @staticmethod
    def get_all(
        user_id: int,
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    title,
                    description,
                    due_date,
                    completed
                FROM tasks
                WHERE user_id = ?
                ORDER BY id DESC
                """,
                (user_id,),
            )

            rows = cursor.fetchall()

            return [
                {
                    "id": row[0],
                    "title": row[1],
                    "description": row[2],
                    "due_date": row[3],
                    "completed": bool(row[4]),
                }
                for row in rows
            ]

        finally:

            conn.close()

    # ==========================
    # Complete
    # ==========================

    @staticmethod
    def complete(
        task_id: int,
        user_id: int,
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE tasks
                SET completed = 1
                WHERE id = ?
                  AND user_id = ?
                  AND completed = 0
                """,
                (
                    task_id,
                    user_id,
                ),
            )

            conn.commit()

            return cursor.rowcount > 0

        finally:

            conn.close()

    # ==========================
    # Delete
    # ==========================

    @staticmethod
    def delete(
        task_id: int,
        user_id: int,
    ):

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM tasks
                WHERE id = ?
                  AND user_id = ?
                """,
                (
                    task_id,
                    user_id,
                ),
            )

            conn.commit()

            return cursor.rowcount > 0

        finally:

            conn.close()

    # ==========================
    # Worker / Due Tasks
    # ==========================

    @staticmethod
    def get_due_tasks():

        conn = get_connection()

        try:

            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id,
                    user_id,
                    title,
                    due_date
                FROM tasks
                WHERE completed = 0
                  AND due_date != ''
                ORDER BY id ASC
                """
            )

            rows = cursor.fetchall()

            now = datetime.now()

            due_tasks = []

            for row in rows:

                due_date = (
                    row[3] or ""
                ).strip()

                if not due_date:
                    continue

                target = None

                # ==========================
                # Full datetime
                # ==========================

                try:

                    target = datetime.strptime(
                        due_date,
                        "%Y-%m-%d %H:%M",
                    )

                except ValueError:
                    pass

                # ==========================
                # Date only
                # ==========================

                if target is None:

                    try:

                        target = datetime.strptime(
                            due_date,
                            "%Y-%m-%d",
                        )

                    except ValueError:

                        continue

                # ==========================
                # Due check
                # ==========================

                if target <= now:

                    due_tasks.append(
                        {
                            "id": row[0],
                            "user_id": row[1],
                            "title": row[2],
                            "due_date": row[3],
                        }
                    )

            return due_tasks

        finally:

            conn.close()