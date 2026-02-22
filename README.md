<!-- vim: set ft=markdown : -->


# Round-robin scheduler

## Summary

The script `scheduler.py` may be used to assign people to groups subject to some constraints.

For example, suppose that every week you would like to organize people into groups of a given size
for an afternoon coffee or walk. However, you don't want to group people if they've recently been
grouped, and you also don't want to group managers with direct reports since they already have
recurring 1:1 meetings. This script can do that.

## Prerequisites

* [mise](https://mise.jdx.dev/)

``` shell
mise run install
mise exec -- pixi shell
```

## Usage

1. Edit the `participant-adjlist` file, which must conform to [NetworkX's adjacency list
   format](https://networkx.org/documentation/stable/reference/readwrite/adjlist.html). For
   [example](https://cdn-cashy-static-assets.lucidchart.com/marketing/blog/2017Q1/7-types-organizational-structure/functional-org-structure-template.png),

    ```text
                                          ┌───────────────┐
                                          │ David Sellner │
                                          └───────┬───────┘
                                                  │
                    ┌─────────────────┬───────────┴───────┬────────────────────┐
                    │                 │                   │                    │
             ┌──────┴──────┐ ┌────────┴────────┐ ┌────────┴─────────┐ ┌────────┴────────┐
             │ Bent Grasha │ │ Birgitta Rosoni │ │ Kendra Scrammage │ │ Mickey Neilands │
             └──────┬──────┘ └─────────────────┘ └────────┬─────────┘ └────────┬────────┘
                    │                                     │                    │
            ┌───────┴──────────┐                   ┌──────┘           ┌────────┴─────────┐
            │                  │                   │                  │                  │
    ┌───────┴────────┐ ┌───────┴───────┐ ┌─────────┴─────────┐ ┌──────┴───────┐ ┌────────┴───────┐
    │ Brigida Withey │ │ Percy Veltman │ │ Berkley Esherwood │ │ Debby Lethem │ │ Matteo Gobeaux │
    └────────────────┘ └───────────────┘ └───────────────────┘ └──────────────┘ └────────────────┘
    ```

   would be represented as

    ```text
    David_Sellner Bent_Grasha Birgitta_Rosoni Kendra_Scrammage Mickey_Neilands
    Bent_Grasha Brigida_Withey Percy_Veltman
    Kendra_Scrammage Berkley_Esherwood
    Mickey_Neilands Debby_Lethem Matteo_Gobeaux
    ```

   in NetworkX's adjacency list format. In this example, Bent may not be grouped with David, Brigida
   or Percy, but may be grouped with anyone else.

1. Edit the `participant-excluded` file, which should either be empty or list one person per line.
   If someone is currently out of office or is otherwise temporarily unavailable, they should be
   listed in this file.

1. Select the desired group size. The script accepts a `--desired-group-size` argument that defaults
   to `2` and may not be less than that.

1. Select the historical solution limit. The script accepts a `--historical-solution-limit` argument
   that defaults to `None` (unbounded lookback window); if specified, it must be a non-negative
   integer.

   Whenever the script is run, a solution (if one exists) is written out to the `solutions`
   directory. When the script is first run, the solution is written to a file named `0`. When next
   run, the next filename is `1`, etc.

   By default, when generating a solution, all groupings from all historical solutions will be
   taken into consideration, and if two people were ever in the same group, they will no longer be
   eligible to be grouped together. Eventually it may become impossible to generate new solutions.

   If this happens, a positive value `N` should be specified so that only the `N` most recent
   historical solutions are taken into consideration. For example, if there are 3 historical
   solutions (with filenames `0`, `1` and `2`) and `N = 2`, then only the two most recent solutions
   `2` and `1` will be taken into consideration.

   Also, if desired `0` may be specified, which causes the solver to ignore any/all historical
   solutions.

1. Run the script with the desired arguments. By default, solutions are written to the `solutions`
   directory. Solution files have one group per line.


    ```shell
    ./scheduler.py --help
    ```

    ```text
    usage: scheduler.py [-h] [--participant-adjlist PARTICIPANT_ADJLIST]
                        [--participant-excluded PARTICIPANT_EXCLUDED] [--solution-dir SOLUTION_DIR]
                        [--desired-group-size DESIRED_GROUP_SIZE]
                        [--historical-solution-limit HISTORICAL_SOLUTION_LIMIT]
                        [--solution-limit SOLUTION_LIMIT]
                        [--log-min-level {NOTSET,DEBUG,INFO,WARNING,ERROR,CRITICAL}]
                        [--log-renderer {auto,console,json}]

    options:
      -h, --help            show this help message and exit
      --participant-adjlist PARTICIPANT_ADJLIST
                            participants in NetworkX's adjacency list format; managers should have
                            edges to their direct reports to avoid grouping managers with their direct
                            reports in the solution:
                            https://networkx.org/documentation/stable/reference/readwrite/adjlist.html
                            (default: participant-adjlist)
      --participant-excluded PARTICIPANT_EXCLUDED
                            participants to be excluded from the solution; useful when someone is out
                            of office (one participant per line) (default: participant-excluded)
      --solution-dir SOLUTION_DIR
                            directory to which the solution will be written and from which historical
                            solutions may be read (solution files have one space-delimited group per
                            line) (default: solutions)
      --desired-group-size DESIRED_GROUP_SIZE
                            desired size of each group in the solution (must not be less than 2)
                            (default: 2)
      --historical-solution-limit HISTORICAL_SOLUTION_LIMIT
                            max number N of most recent historical solutions to account for when
                            generating the next solution; if two participants were in the same group
                            in any of the N most recent historical solutions, they will not be
                            assigned to the same group (None makes N infinite, 0 disables this
                            constraint) (default: None)
      --solution-limit SOLUTION_LIMIT
                            max number N of solutions to generate; this option is primarily for
                            exploratory purposes and should normally be set to 1 (default: 1)
      --log-min-level {NOTSET,DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            only process log records at this level or greater (default: INFO)
      --log-renderer {auto,console,json}
                            auto: "console" if stdout is a TTY, otherwise "json" (default: auto)
    ```

## Example

``` shell
./scheduler.py | jq .
```

``` json
{
  "status": "FEASIBLE",
  "solutions_found": 1,
  "wall_time": 0.006301,
  "branches": 156,
  "conflicts": 0,
  "event": "finish",
  "level": "info",
  "timestamp": "2023-08-31T14:32:58.272988Z"
}
```

``` shell
column -t -- solutions/0
```

``` text
Bent_Grasha        Debby_Lethem
Berkley_Esherwood  Percy_Veltman
Birgitta_Rosoni    Mickey_Neilands
Brigida_Withey     David_Sellner
Kendra_Scrammage   Matteo_Gobeaux
```
