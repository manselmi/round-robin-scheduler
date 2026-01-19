# vim: set ft=python :

import functools
import itertools
import operator
import re
from collections import Counter
from numbers import Integral
from pathlib import Path

import networkx as nx
import structlog
from ortools.sat.python.cp_model import (
    FEASIBLE,
    INFEASIBLE,
    OPTIMAL,
    UNKNOWN,
    CpModel,
    CpSolver,
    CpSolverSolutionCallback,
    Domain,
)

logger = structlog.get_logger(__name__)


class Model:
    def __init__(
        self,
        *,
        participant_graph,
        desired_group_size,
        solution_dir,
        historical_solution_limit,
    ):
        if not (
            isinstance(participant_graph, nx.DiGraph)
            and all(isinstance(node, str) for node in participant_graph)
        ):
            msg = "participant_graph must be a directed graph with nodes of type str"
            raise TypeError(msg)

        num_participants = len(participant_graph)
        if num_participants < 2:
            msg = "participant_graph must have at least two nodes"
            raise ValueError(msg)

        if not isinstance(desired_group_size, Integral):
            msg = "desired_group_size must be an Integral"
            raise TypeError(msg)

        if desired_group_size < 2:
            msg = "desired_group_size must be at least 2"
            raise ValueError(msg)

        if num_participants < desired_group_size:
            msg = "num_participants must be greater than or equal to desired_group_size"
            raise ValueError(msg)

        if not isinstance(solution_dir, Path):
            msg = "solution_dir must ba a Path"
            raise TypeError(msg)

        if not isinstance(historical_solution_limit, type(None) | Integral):
            msg = "historical_solution_limit must be None or an Integral"
            raise TypeError(msg)

        if historical_solution_limit is not None and historical_solution_limit < 0:
            msg = "historical_solution_limit may not be less than 0"
            raise ValueError(msg)

        participants = sorted(participant_graph)

        model = CpModel()
        variables = []
        for _, row in itertools.groupby(
            itertools.product(participants, repeat=2),
            key=operator.itemgetter(0),
        ):
            variables.append([model.NewBoolVar("{} {}".format(*pair)) for pair in row])

        self._desired_group_size = desired_group_size
        self._historical_solution_limit = historical_solution_limit
        self._model = model
        self._num_participants = num_participants
        self._participants = participants
        self._participant_graph = participant_graph
        self._solution_dir = solution_dir
        self._variables = variables

        self._apply_no_self_pair_constraint()
        self._apply_symmetric_constraint()
        self._apply_transitive_constraint()
        self._apply_group_size_constraint()
        self._apply_hierarchical_constraint()
        self._apply_historical_constraint()

    def solve(self, *, solution_limit):
        if not isinstance(solution_limit, Integral):
            msg = "solution_limit must be an Integral"
            raise TypeError(msg)

        if solution_limit < 0:
            msg = "solution_limit may not be less than 0"
            raise ValueError(msg)

        solution_name = str(
            1
            + max(
                (int(path.name) for path in self._solution_paths()),
                default=-1,
            )
        )

        solver = CpSolver()
        callback = ModelSolutionCallback(
            variables=self._variables,
            solution_dir=self._solution_dir,
            solution_name=solution_name,
            solution_limit=solution_limit,
        )

        status = solver.SearchForAllSolutions(self._model, callback)

        event = "finish"
        log = logger.bind(status=solver.StatusName(status))

        if status not in {FEASIBLE, INFEASIBLE, OPTIMAL, UNKNOWN}:
            log.error(event)
            return

        log = log.bind(
            solutions_found=callback.solution_count,
            wall_time=solver.WallTime(),
            branches=solver.NumBranches(),
            conflicts=solver.NumConflicts(),
        )

        if status in {FEASIBLE, OPTIMAL}:
            log.info(event)
        else:
            log.warning(event)

    def _apply_no_self_pair_constraint(self):
        for i in range(self._num_participants):
            self._model.Add(self._variables[i][i] == 0)

    def _apply_symmetric_constraint(self):
        N = self._num_participants
        for i in range(N - 1):
            for j in range(i + 1, N):
                self._model.Add(self._variables[i][j] == self._variables[j][i])

    def _apply_transitive_constraint(self):
        N = self._num_participants
        for i in range(N - 2):
            for j in range(i + 1, N - 1):
                for k in range(j + 1, N):
                    self._model.Add(
                        sum([
                            self._variables[i][j],
                            self._variables[i][k],
                            self._variables[j][k],
                        ])
                        != 2
                    )

    def _apply_group_size_constraint(self):
        group_sizes = self._compute_group_sizes()

        row_sums = []
        for group_size, group_size_count in group_sizes.items():
            row_sums.extend([group_size - 1] * group_size * group_size_count)
        self._model.Add(
            sum(row_sums)
            == sum(
                self._variables[i][j]
                for i, j in itertools.product(
                    range(self._num_participants),
                    repeat=2,
                )
            )
        )

        domain = Domain.FromValues(row_sums)
        for row in self._variables:
            self._model.AddLinearExpressionInDomain(sum(row), domain)

    def _compute_group_sizes(self):
        desired_group_size = self._desired_group_size
        num_participants = self._num_participants

        group_sizes = Counter()
        quotient, remainder = divmod(num_participants, desired_group_size)
        group_sizes[desired_group_size] = quotient

        if remainder == 0:
            pass
        elif remainder == 1:
            group_sizes[desired_group_size] -= 1
            group_sizes[desired_group_size + remainder] = 1
        else:
            group_sizes[remainder] = 1

        return +group_sizes

    def _apply_hierarchical_constraint(self):
        for parent, child in self._participant_graph.edges():
            i = self._participants.index(parent)
            j = self._participants.index(child)
            self._model.Add(self._variables[i][j] == 0)

    def _apply_historical_constraint(self):
        composed_hs = functools.reduce(
            nx.compose,
            self._historical_solutions(),
            nx.Graph(),
        )

        for pair in itertools.combinations(self._participants, r=2):
            if composed_hs.has_edge(*pair):
                i = self._participants.index(pair[0])
                j = self._participants.index(pair[1])
                self._model.Add(self._variables[i][j] == 0)

    def _historical_solutions(self):
        hs_paths = sorted(
            self._solution_paths(),
            key=lambda path: int(path.name),
            reverse=True,
        )[: self._historical_solution_limit]

        for hs_path in hs_paths:
            hs = nx.Graph()
            with hs_path.open() as fobj:
                for line in filter(lambda line: not line.startswith("#"), fobj):
                    group = line.strip().split()
                    for pair in itertools.combinations(group, r=2):
                        hs.add_edge(*pair)
            yield hs

    def _solution_paths(self):
        pattern = re.compile(r"[0-9]+")

        def predicate(path):
            return path.is_file() and pattern.fullmatch(path.name)

        return filter(predicate, self._solution_dir.iterdir())


class ModelSolutionCallback(CpSolverSolutionCallback):
    def __init__(self, variables, solution_dir, solution_name, solution_limit):
        super().__init__()
        self._solution_dir = solution_dir
        self._solution_name = solution_name
        self.__solution_count = 0
        self.__solution_limit = solution_limit
        self.__variables = variables

    def on_solution_callback(self):
        solution = nx.Graph()

        N = len(self.__variables)
        for i in range(N - 1):
            for j in range(i + 1, N):
                variable = self.__variables[i][j]
                if self.Value(variable) == 1:
                    solution.add_edge(*variable.Name().split())

        groups = sorted(sorted(group) for group in nx.connected_components(solution))

        path = self._solution_dir.joinpath(
            self._solution_name
            if self.__solution_limit == 1
            else "_".join([self._solution_name, str(self.__solution_count)])
        )
        with path.open(mode="wt") as fobj:
            for group in groups:
                fobj.write(" ".join(group))
                fobj.write("\n")

        self.__solution_count += 1
        if 0 < self.__solution_limit <= self.__solution_count:
            self.StopSearch()

    @property
    def solution_count(self):
        return self.__solution_count
