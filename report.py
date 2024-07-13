#!/usr/bin/env python3

import collections
import pathlib
import re
import tempfile
import zipfile

import click
import hytek_parser
import numpy as np
from scipy.interpolate import interp1d
import matplotlib.patches as mpatches
import matplotlib


@click.group()
def cli():
    """dolphins cli help text"""
    pass


def file_stream(top):
    """
    given a top directory spit out all of the .hy3 files below that point, including ones inside .zip files
    """
    path = pathlib.Path(top)
    for p in path.rglob("*"):
        if p.name.endswith(".zip"):
            archive = zipfile.ZipFile(p, "r")
            with tempfile.TemporaryDirectory() as tempdir:
                archive.extractall(tempdir)
                for zippath in pathlib.Path(tempdir).rglob("*"):
                    if zippath.suffix == ".hy3":
                        yield zippath
        elif p.suffix == ".hy3":
            yield p


def events(src):
    """
    spit out a time ordered stream of events (swimmer, entry, details)
    """

    outs = []
    for afile in src:
        print(afile)
        ht = hytek_parser.parse_hy3(afile)

        for event in ht.meet.events.values():
            for entry in event.entries:
                if len(entry.swimmers) != 1:
                    # print(" skip multiswimmer event",y.stroke.name, y.distance)
                    continue
                for aswimmer in entry.swimmers:
                    if entry.finals_time == 0:
                        continue
                    outs.append({"swimmer": aswimmer, "entry": entry, "details": event})

    for anout in sorted(outs, key=lambda x: x["entry"].finals_date):
        yield anout


@cli.command(name="compare")
@click.option("--dir", "adir", help="recurively search below")
def compare(adir):

    mem = collections.defaultdict(lambda: collections.defaultdict(dict))
    event_mem = collections.defaultdict(lambda: collections.defaultdict(dict))
    swim_dates_set = set()
    for event in events(file_stream(adir)):
        # if 'Cariaso' not in event['swimmer'].last_name:
        #    continue
        swimmer_key = (event["swimmer"].last_name, event["swimmer"].first_name)
        event_key = (event["details"].distance, event["details"].stroke.name)
        swim_date = event["entry"].finals_date
        final_time = event["entry"].finals_time
        swim_dates_set.add(swim_date)
        # print(f"  :{event['details'].distance:>5d} {event['details'].stroke.name:<15s}: {event['entry'].finals_date} {event['entry'].finals_time:>10.2f} {event['swimmer'].first_name} {event['swimmer'].last_name}")
        mem[swimmer_key][event_key][swim_date] = final_time
        event_mem[event_key][swimmer_key][swim_date] = final_time

    swim_dates = list(sorted(swim_dates_set))
    swim_dates_idx = list(range(len(swim_dates)))
    swim_dates_table = {x: y for x, y in zip(swim_dates, swim_dates_idx)}

    import matplotlib.pyplot as plt

    worst_times = {}
    best_times = {}
    for swimmer, swimmer_vals in mem.items():
        for event, event_vals in swimmer_vals.items():
            for swim_date, final_time in event_vals.items():
                if event not in worst_times:
                    worst_times[event] = final_time
                elif final_time > worst_times[event]:
                    worst_times[event] = final_time
                if event not in best_times:
                    best_times[event] = final_time
                elif final_time < best_times[event]:
                    best_times[event] = final_time

    if make_by_swimmer := True:

        import imageio

        images_by_event = {}
        for swimmer, swimmer_vals in sorted(mem.items()):

            for event, event_vals in swimmer_vals.items():

                if event not in images_by_event:
                    images_by_event[event] = imageio.get_writer(
                        f"images/anim/{event[0]}_{event[1]}.gif",
                        mode="I",
                        duration=1000,
                        loop=0,
                    )

                if len(event_vals) > 1:

                    x_label = []
                    x = []
                    y = []
                    n = []

                    for swim_date, final_time in event_vals.items():
                        print(swimmer, event, swim_date, final_time)
                        x_label.append(swim_date)
                        y.append(final_time)
                        n.append(final_time)
                    x = list(range(len(x_label)))

                    plt.clf()
                    plt.plot(x, y)
                    plt.ylim(ymin=best_times[event])
                    plt.ylim(ymax=worst_times[event])
                    for i, txt in enumerate(n):
                        plt.annotate(txt, (x[i], y[i]))
                    plt.xticks(x, x_label, rotation="vertical")

                    plt.title(f"{swimmer[0]} {swimmer[1]} {event}")
                    filename_part = safe_filename(
                        f"{swimmer[0]}_{swimmer[1]}_{event[0]}_{event[1]}"
                    )
                    filename = f"images/by-swimmer/{filename_part}.png"

                    print(filename)
                    ensure_parent(filename)
                    plt.savefig(filename)
                    image = imageio.imread(filename)
                    images_by_event[event].append_data(image)

    if make_by_event := True:
        min_events = 2
        for event, event_vals in sorted(event_mem.items()):

            print(event)
            plt.clf()

            fig = plt.figure()
            fig, axs = plt.subplots(
                1,
                1,
                # figsize=(8, 12),
                layout="constrained",
            )
            # ax = plt.subplot(111)

            x = swim_dates
            y = {}
            for swimmer, swimmer_vals in sorted(event_vals.items()):
                if len(event_vals) > 1:
                    swimmer_event = [None] * len(swim_dates)
                    for swim_date, final_time in swimmer_vals.items():
                        if final_time:
                            swimmer_event[swim_dates_table[swim_date]] = final_time
                    #     print(
                    #         swim_dates_table[swim_date],
                    #         swim_date,
                    #         final_time,
                    #         swimmer,
                    #         event,
                    #     )
                    # print("  ==")
                    if len([x for x in swimmer_event if x]) >= min_events:
                        y[swimmer] = swimmer_event
                        print("    ", event, swimmer, "\t\t", y[swimmer])

            plt.ylim(ymin=best_times[event])
            plt.ylim(ymax=worst_times[event])

            handles, labels = plt.gca().get_legend_handles_labels()
            colors = matplotlib.cm.tab20(range(len(y)))
            for i_swimmer, swimmer in enumerate(y):

                c = colors[i_swimmer]
                print("  ~~ ", str(swimmer), "\t\t", y[swimmer])
                axs.plot(
                    x,
                    interpolate_missing(swim_dates_idx, y[swimmer]),
                    marker="+",
                    linestyle="dotted",
                    linewidth=0.5,
                    label=str(swimmer),
                    color=c,
                )
                axs.plot(x, y[swimmer], "-o", color=c)  # , label=str(swimmer))
            else:
                print("skip", str(swimmer))

            plt.xticks(x, rotation="vertical")
            fig.legend(loc="outside right", ncol=1)
            plt.title(f"{event}")
            filename_part = safe_filename(
                f"{swimmer[0]}_{swimmer[1]}_{event[0]}_{event[1]}"
            )
            filename = f"images/by-event/{event[0]}_{event[1]}.png"

            print(filename)
            ensure_parent(filename)
            plt.savefig(filename)


def interpolate_missing(x, y):
    x = np.array(x)
    y = np.array(y, dtype=np.float64)
    mask = ~np.isnan(y)
    interp_func = interp1d(
        x[mask], y[mask], kind="linear", bounds_error=False, fill_value="extrapolate"
    )
    return interp_func(x)


def safe_filename(filename):
    clean = re.sub(r"[/\\?%*:|\"<>\x7F\x00-\x1F ]", "-", filename)
    return clean


def ensure_parent(filename):
    pathlib.Path(filename).parents[0].mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    cli()
