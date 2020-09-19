publish
=======

A tool to build and publish certain artifacts at certain times.

*publish* was designed specifically for the automatic publication of course
materials, such as homeworks, lecture slides, etc.

Example
-------

Suppose we have a collection of homeworks written in LaTeX and a collection of
labs in the form of Jupyter notebooks, all within a folder named `course`

```text
course/
|-- homeworks
|   |-- 01-intro
|   |   |-- Makefile
|   |   |-- solutions.tex
|   |   `-- homework.tex
|   `-- 02-python
|       |-- Makefile
|       |-- solutions.tex
|       `-- homework.tex
`-- labs
    `-- 01-intro
        `-- lab.ipynb
```

We'd like to automatically publish these assignments to our course webpage. Of
course, the homeworks must be compiled into PDFs first, and we definitely
shouldn't publish the solutions before the due date! We also would like a
standardized way of keeping track of each assignment's due date, name etc. so
that they appear correctly on our course webpage.

Here is where *publish* comes in. We can tell *publish* how and when to build
files by creating a `publish.yaml` file.

```yaml
# course/homeworks/01-intro/publish.yaml
artifacts:
    homework.pdf:
        recipe: make
    solution.pdf:
        recipe: make solution
        release_time: 2020-09-21 23:59:00

```

This tells *publish* how to create *two* files, or *artifacts*: `homework.pdf`
and `solution.pdf`. To build the solution, for instance, *publish* will execute
`make solution` in the directory containing the `publish.yaml`. But it will
*only* do this if the current time is after the artifact's release time.
We'll create `publish.yaml` files for everything we want to build and publish.

But remember that we also want to keep track of the due date, assignment name,
etc. We can do so by adding metadata to `publish.yaml`:

```yaml
# course/homeworks/01-intro/publish.yaml
metadata:
    name: Homework 01
    due: 2020-09-20 23:59:00

artifacts:
    homework.pdf:
        recipe: make
    solution.pdf:
        recipe: make solution
        release_time: 2020-09-21 23:59:00
```

In this case, we apparently want to release the solution 24 hours after the
assignment is due. It's nicer and less error-prone for us to write the release
time this way:

```yaml
# course/homeworks/01-intro/publish.yaml
metadata:
    name: Homework 01
    due: 2020-09-20 23:59:00

artifacts:
    homework.pdf:
        recipe: make
    solution.pdf:
        recipe: make solution
        release_time: 1 day after metadata.due
```

If we have a script that builds our course page, we'd like it to be able to
print every published homework and its due date. To make this easy, we want
every homework to have the same artifacts and metadata. We can enforce this by
writing a `collection.yaml` file in the `homeworks` directory:

```yaml
# course/homeworks/collection.yaml
schema:
    required_artifacts:
        - homework.pdf
        - solution.pdf

    metadata_schema:
        name:
            type: str
        due:
            type: datetime
```

This tells *publish* that all publications found below `homeworks/` need to have
these two artifacts, and their metadata should include a `name` field with a
string value and a `due` field with a datetime value.

Now we're ready to publish. In the same directory as `input/`, run:

```bash
> publish input output
```

This will build all artifacts under the `input/` directory whose release time
has passed and copy them over to the output directory. It will also output a
file, `output/published.json`, containing all metadata about the published
artifacts and where they can be found.

Maybe we want to publish all of the solutions to another directory for our
course staff to use, even if they haven't been released yet:

```bash
> publish input staff-output --artifact-filter solution.pdf --ignore-release-time
```

Or maybe we only want to publish homeworks:

```bash
> publish input output --skip-directories labs
```

That's pretty much it. See https://eldridgejm.github.io/publish/ for the full
documentation. 
