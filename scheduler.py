#!/usr/bin/env python
# vim: set ft=python :

import argparse
from pathlib import Path

import networkx as nx
import structlog

from model import Model
from structlog_config import Level, LevelName, Renderer, configure_structlog
from structlog_processors import graph_transformer

THIS_FILE = Path(__file__)

logger = structlog.get_logger(__name__)


def main(
    *,
    participant_adjlist,
    participant_excluded,
    solution_dir,
    desired_group_size,
    historical_solution_limit,
    solution_limit,
):
    log = logger.bind()
    participant_graph = nx.read_adjlist(
        participant_adjlist,
        create_using=nx.DiGraph,
    )
    log.debug("participants", graph=participant_graph)
    participant_excluded_graph = nx.read_adjlist(
        participant_excluded,
    )
    log.debug("excluded", graph=participant_excluded_graph)
    for node in participant_excluded_graph:
        participant_graph.remove_node(node)
    log.debug("participants - excluded", graph=participant_graph)

    model = Model(
        participant_graph=participant_graph,
        desired_group_size=desired_group_size,
        solution_dir=solution_dir,
        historical_solution_limit=historical_solution_limit,
    )
    model.solve(solution_limit=solution_limit)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--participant-adjlist",
        type=Path,
        default=THIS_FILE.with_name("participant-adjlist"),
        help=(
            "participants in NetworkX's adjacency list format; "
            "managers should have edges to their direct reports to "
            "avoid grouping managers with their direct reports in the "
            "solution: "
            "https://networkx.org/documentation/stable/reference/readwrite/adjlist.html"
        ),
    )
    parser.add_argument(
        "--participant-excluded",
        type=Path,
        default=THIS_FILE.with_name("participant-excluded"),
        help=(
            "participants to be excluded from the solution; useful "
            "when someone is out of office (one participant per line)"
        ),
    )
    parser.add_argument(
        "--solution-dir",
        type=Path,
        default=THIS_FILE.with_name("solutions"),
        help=(
            "directory to which the solution will be written and from "
            "which historical solutions may be read (solution files "
            "have one space-delimited group per line)"
        ),
    )
    parser.add_argument(
        "--desired-group-size",
        type=int,
        default=2,
        help="desired size of each group in the solution (must not be less than 2)",
    )
    parser.add_argument(
        "--historical-solution-limit",
        type=int,
        default=None,
        help=(
            "max number N of most recent historical solutions to "
            "account for when generating the next solution; if two "
            "participants were in the same group in any of the N most "
            "recent historical solutions, they will not be assigned to "
            "the same group (None makes N infinite, 0 disables this "
            "constraint)"
        ),
    )
    parser.add_argument(
        "--solution-limit",
        type=int,
        default=1,
        help=(
            "max number N of solutions to generate; this option is "
            "primarily for exploratory purposes and should normally be "
            "set to 1"
        ),
    )
    parser.add_argument(
        "--log-min-level",
        type=LevelName,
        default=LevelName.INFO,
        choices=list(LevelName),
        help="only process log records at this level or greater",
    )
    parser.add_argument(
        "--log-renderer",
        type=Renderer,
        default=Renderer.AUTO,
        choices=list(Renderer),
        help=f'auto: "{Renderer.CONSOLE}" if stdout is a TTY, otherwise "{Renderer.JSON}"',
    )

    args = parser.parse_args()

    configure_structlog(
        min_level=Level[args.log_min_level],
        processors=[graph_transformer],
        renderer=args.log_renderer,
    )

    main(
        participant_adjlist=args.participant_adjlist,
        participant_excluded=args.participant_excluded,
        solution_dir=args.solution_dir,
        desired_group_size=args.desired_group_size,
        historical_solution_limit=args.historical_solution_limit,
        solution_limit=args.solution_limit,
    )
