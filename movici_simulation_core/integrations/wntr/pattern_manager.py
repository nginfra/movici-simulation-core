"""Pattern management for WNTR demand and head patterns"""

from __future__ import annotations

import typing as t

import numpy as np


class PatternManager:
    """Manages WNTR patterns from Movici tape files and configuration

    Patterns in WNTR are time-varying multipliers applied to base demands,
    reservoir heads, and pump speeds. This manager handles creating patterns
    from tape file data and updating them during simulation.
    """

    def __init__(self, wn):
        """Initialize pattern manager

        :param wn: WNTR WaterNetworkModel instance
        """
        self.wn = wn
        self.active_patterns: t.Dict[str, t.Any] = {}
        self.pattern_timestep = 3600  # Default 1 hour in seconds

    def set_pattern_timestep(self, timestep: int):
        """Set the pattern timestep in seconds

        :param timestep: Pattern timestep in seconds
        """
        self.pattern_timestep = timestep

    def create_pattern(
        self, pattern_name: str, multipliers: t.List[float], wrap: bool = True
    ) -> t.Any:
        """Create a pattern in the WNTR model

        :param pattern_name: Name of the pattern
            :param multipliers: List of multiplier values
            wrap: If True, pattern repeats; if False, returns 0 after end

        :return: WNTR Pattern object
        """
        try:
            # Check if pattern already exists
            if pattern_name in self.wn.pattern_name_list:
                pattern = self.wn.get_pattern(pattern_name)
                # Update existing pattern
                pattern.multipliers = multipliers
            else:
                # Create new pattern
                pattern = self.wn.add_pattern(pattern_name, multipliers)
                if hasattr(pattern, "wrap"):
                    pattern.wrap = wrap

            self.active_patterns[pattern_name] = pattern
            return pattern
        except Exception as e:
            raise ValueError(f"Failed to create pattern '{pattern_name}': {e}") from e

    def update_pattern(self, pattern_name: str, multipliers: t.List[float]):
        """Update an existing pattern's multipliers

        :param pattern_name: Name of the pattern to update
            :param multipliers: New multiplier values
        """
        if pattern_name not in self.wn.pattern_name_list:
            raise ValueError(f"Pattern '{pattern_name}' does not exist")

        pattern = self.wn.get_pattern(pattern_name)
        pattern.multipliers = multipliers
        self.active_patterns[pattern_name] = pattern

    def get_pattern(self, pattern_name: str) -> t.Any:
        """Get a pattern by name

        :param pattern_name: Name of the pattern

        :return: WNTR Pattern object
        """
        if pattern_name in self.active_patterns:
            return self.active_patterns[pattern_name]
        return self.wn.get_pattern(pattern_name)

    def remove_pattern(self, pattern_name: str):
        """Remove a pattern from the model

        :param pattern_name: Name of the pattern to remove
        """
        if pattern_name in self.wn.pattern_name_list:
            self.wn.remove_pattern(pattern_name)
        if pattern_name in self.active_patterns:
            del self.active_patterns[pattern_name]

    def get_all_patterns(self) -> t.Dict[str, t.Any]:
        """Get all patterns in the model

        :return: Dictionary mapping pattern names to Pattern objects
        """
        return {name: self.wn.get_pattern(name) for name in self.wn.pattern_name_list}

    def create_constant_pattern(self, pattern_name: str, value: float = 1.0) -> t.Any:
        """Create a constant pattern (single multiplier value)

        :param pattern_name: Name of the pattern
            :param value: Constant multiplier value

        :return: WNTR Pattern object
        """
        return self.create_pattern(pattern_name, [value], wrap=True)

    def create_daily_pattern(self, pattern_name: str, hourly_multipliers: t.List[float]) -> t.Any:
        """Create a daily repeating pattern (24 hourly values)

        :param pattern_name: Name of the pattern
            :param hourly_multipliers: List of 24 hourly multiplier values

        :return: WNTR Pattern object
        """
        if len(hourly_multipliers) != 24:
            raise ValueError(f"Daily pattern requires 24 values, got {len(hourly_multipliers)}")
        return self.create_pattern(pattern_name, hourly_multipliers, wrap=True)

    def interpolate_pattern(
        self, pattern_name: str, time_value_pairs: t.List[t.Tuple[float, float]]
    ) -> t.Any:
        """Create a pattern from time-value pairs with linear interpolation

        :param pattern_name: Name of the pattern
            :param time_value_pairs: List of (time_hours, multiplier) tuples

        :return: WNTR Pattern object
        """
        if not time_value_pairs:
            raise ValueError("time_value_pairs cannot be empty")

        # Sort by time
        time_value_pairs = sorted(time_value_pairs, key=lambda x: x[0])

        # Extract times and values
        times = np.array([t for t, v in time_value_pairs])
        values = np.array([v for t, v in time_value_pairs])

        # Create interpolation points at pattern timestep intervals
        timestep_hours = self.pattern_timestep / 3600.0
        max_time = times[-1]
        interp_times = np.arange(0, max_time + timestep_hours, timestep_hours)

        # Interpolate values
        interp_values = np.interp(interp_times, times, values)

        return self.create_pattern(pattern_name, interp_values.tolist(), wrap=False)

    def apply_pattern_to_junction(self, junction_name: str, pattern_name: str):
        """Apply a demand pattern to a junction

        :param junction_name: Name of the junction
            :param pattern_name: Name of the pattern to apply
        """
        try:
            junction = self.wn.get_node(junction_name)
            if hasattr(junction, "demand_timeseries_list"):
                # WNTR 1.0+ API
                if len(junction.demand_timeseries_list) > 0:
                    junction.demand_timeseries_list[0].pattern_name = pattern_name
                else:
                    junction.add_demand(base=junction.base_demand, pattern_name=pattern_name)
            else:
                # Legacy API
                junction.demand_pattern_name = pattern_name
        except Exception as e:
            raise ValueError(
                f"Failed to apply pattern '{pattern_name}' to junction '{junction_name}': {e}"
            ) from e

    def apply_pattern_to_reservoir(self, reservoir_name: str, pattern_name: str):
        """Apply a head pattern to a reservoir

        :param reservoir_name: Name of the reservoir
            :param pattern_name: Name of the pattern to apply
        """
        try:
            reservoir = self.wn.get_node(reservoir_name)
            if hasattr(reservoir, "head_pattern_name"):
                reservoir.head_pattern_name = pattern_name
            else:
                raise AttributeError("Reservoir does not support head patterns")
        except Exception as e:
            raise ValueError(
                f"Failed to apply pattern '{pattern_name}' to reservoir '{reservoir_name}': {e}"
            ) from e
