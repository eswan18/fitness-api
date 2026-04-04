from fitness.models.lift import Lift, ExerciseTemplate


def compute_lift_stats(
    all_lifts: list[Lift],
    period_lifts: list[Lift],
) -> dict:
    """Compute aggregated lifting statistics.

    Args:
        all_lifts: All lifts for all-time totals.
        period_lifts: Lifts in the selected period for period-specific stats.

    Returns:
        Dict with keys matching LiftStatsResponse fields.
    """
    total_sessions = len(all_lifts)
    total_volume = sum(lift.total_volume() for lift in all_lifts)
    total_sets = sum(lift.total_sets() for lift in all_lifts)
    duration_all_time = sum(lift.duration_seconds() for lift in all_lifts)

    duration_in_period = sum(lift.duration_seconds() for lift in period_lifts)
    avg_duration = round(duration_in_period / len(period_lifts)) if period_lifts else 0

    rpe_values = [
        s.rpe
        for lift in period_lifts
        for exercise in lift.exercises
        for s in exercise.sets
        if s.set_type != "warmup" and s.rpe is not None
    ]
    avg_rpe = round(sum(rpe_values) / len(rpe_values), 1) if rpe_values else None

    return dict(
        total_sessions=total_sessions,
        total_volume_kg=total_volume,
        total_sets=total_sets,
        duration_all_time_seconds=duration_all_time,
        sessions_in_period=len(period_lifts),
        volume_in_period_kg=sum(lift.total_volume() for lift in period_lifts),
        sets_in_period=sum(lift.total_sets() for lift in period_lifts),
        duration_in_period_seconds=duration_in_period,
        avg_duration_seconds=avg_duration,
        avg_rpe=avg_rpe,
    )


def compute_volume_by_muscle(
    lifts: list[Lift],
    templates: list[ExerciseTemplate],
) -> list[dict]:
    """Compute volume (weight x reps) grouped by primary muscle group.

    Returns non-warmup set volume by muscle group, sorted descending.
    """
    template_muscle_map = {t.id: t.primary_muscle_group for t in templates}

    muscle_volume: dict[str, float] = {}
    for lift in lifts:
        for exercise in lift.exercises:
            exercise_id = exercise.exercise_template_id
            if exercise_id is None:
                continue
            muscle = template_muscle_map.get(exercise_id)
            if muscle:
                vol = sum(s.volume() for s in exercise.sets if s.set_type != "warmup")
                muscle_volume[muscle] = muscle_volume.get(muscle, 0) + vol

    sorted_muscles = sorted(muscle_volume.items(), key=lambda x: x[1], reverse=True)
    return [{"muscle": m, "volume": round(v, 1)} for m, v in sorted_muscles]


def compute_sets_by_muscle(
    lifts: list[Lift],
    templates: list[ExerciseTemplate],
) -> list[dict]:
    """Count non-warmup sets grouped by primary muscle group, sorted descending."""
    template_muscle_map = {t.id: t.primary_muscle_group for t in templates}

    muscle_sets: dict[str, int] = {}
    for lift in lifts:
        for exercise in lift.exercises:
            exercise_id = exercise.exercise_template_id
            if exercise_id is None:
                continue
            muscle = template_muscle_map.get(exercise_id)
            if muscle:
                non_warmup = sum(1 for s in exercise.sets if s.set_type != "warmup")
                muscle_sets[muscle] = muscle_sets.get(muscle, 0) + non_warmup

    sorted_muscles = sorted(muscle_sets.items(), key=lambda x: x[1], reverse=True)
    return [{"muscle": m, "sets": s} for m, s in sorted_muscles]
