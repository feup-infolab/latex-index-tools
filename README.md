# latex-index-tools

LaTeX index generation tools for dissertations, theses, books, or reports.

While nothing replaces the manual selection of concepts to add to your back-of-the-book index, we can make this job easier by relying on automatic tools. LaTeX Index Tools enables you to automatically extract the most salient concepts, via keyword extraction, providing an easy way to edit them and add additional matching expressions for the same index entry:

```shell
./extract_concepts.py -i thesis.tex \
  -o reviewed_concepts.csv -ml 2 -n 1000 -m rake -s
```

This will use `detex` to extract the text from the LaTeX document, considering the content from any `\input` and `\include`. The extracted keywords will be saved to a CSV file with three columns: `concept`, `match` and `weight`. The `concept` is the same as the index entry, while `match` is the text after which the index entry should be added --- thus, multiple rows containing the same `concept`, but different `match` entries can be added. In this example, the minimum length of concepts is 2, and we extract 1000 concepts using RAKE. The `-s` option is used to provide an interactive command line review of concepts. It can be removed for a fully automatic extraction process, or when manually editting the resulting CSV file is preferred.

After the CSV file containing concepts and matches is prepared, we can automatically add the index entries to our LaTeX files:

```shell
./index_concepts.py -i thesis.tex -c reviewed_concepts.csv \
  -o /tmp/output_dir -e arsclassica-settings.tex \
  -e listings-settings.tex -e hyphenations.tex -e "FrontBackMatter/*.tex" \
  -m stop -m dist
```

All LaTeX files within the `thesis.tex` directory are considered. We do not parse the main LaTeX to find dependencies. Instead, we simply consider all `*.tex` files, recursively, excluding those that do not matter using the `-e` option. No chances will be done to your files. Instead, a new copy will be created in the directory pointed out by `-o`. We also provide heuristics to avoid overcrowding the back-of-the-book index:

- `stop`, which relies on the `THESIS_STOPWORDS` constant within `index_concepts.py`, which you can edit to setup your own stopword-like concepts to be ignored (use the distribution of concepts provided as output of this script to and a cutoff of about 100, at most, to select these stopwords;
- `dist` will ensure a given distance (set in the `DISTANCE` constant withint `index_concepts.py`) in number of lines between concept mentions (this is reset between chapters).
