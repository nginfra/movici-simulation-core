from movici_simulation_core.models.common.csv_tape import CsvTape
from movici_simulation_core.models.traffic_demand_calculation.common import GlobalContributor


class ScalarParameter(GlobalContributor):
    def update_factor(self, factor: float, **_) -> float:
        return factor * self.get_value()


class GlobalElasticityParameter(GlobalContributor):
    """
    Formulation: F_ij = (GP_n / GP_(n-1))_i ** (eta) * (GP_n / GP_(n-1))_j ** (eta)
        F_ij: Multiplication factor for demand from node i to node j
        GP: Global Parameter
        n: iteration number (eg: year)
        eta: elasticity
    """

    def __init__(self, parameter: str, csv_tape: CsvTape, elasticity: float):
        super().__init__(parameter, csv_tape)
        self.elasticity = elasticity
        self.curr = self.get_value()

    def update_factor(self, factor: float, **_) -> float:
        new_val = self.get_value()
        result = factor * self.get_factor(new_val)
        self.reset_value()
        return result

    def get_factor(self, value):
        #  since GP_ni == GP_nj for global parameters, we can multiply the exponent by 2
        if value == 0 or self.curr == 0:
            return 1
        return (value / self.curr) ** (2 * self.elasticity)

    def reset_value(self):
        self.curr = self.get_value()
