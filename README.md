# Review of literature covering selection in plants

## Primary goals
- Identify publications reporting whole genome resequencing in plants
- Find how frequently various types of selection are reported
- Identify details of this reporting, including mentions of selection coefficients and genes involved
- Summarize quantitative results

## Challenges
- No single search term can identify studies focused on plants resequencing
- For both licensing and tractability reasons, searching text (Markdown) versions of manuscripts is most efficient
- 

## Searching the literature
- We focus on PubMed searches because [elinks][1] provides easy access to HTML versions of papers in the public domain.
- Searching with any term can trigger [MeSH][2] terms. This is typically useful, but we have many terms we don't want to include, like plastid sequences or exome capture.
- The [elink][3] tool finds similar papers. We generated a curated list of paper PubMed IDs (PMIDs) that are typical of the type of papers we'd like to find, then use these as "seeds" to find related papers. Papers that match multiple seeds are more likely to be on topic. 
- The script [pubmed_elink.sh][4] implements this strategy, but we ultimately need a list of PMIDs to exclude and a list of search terms we do and do not want to include. Each of the curated papers is treated as a "seed" and we can focus on papers that are found by multiple seeds. The script creates list of papers based on the number of seeds they identify.

## Converting PubMed IDs (PMIDs) to PubMed Central IDs (PMC) and downloading HTML versions
- PMIDs need to be converted to PMC IDs to retrieve full-text versions of papers.
- 



[1]: https://www.ncbi.nlm.nih.gov/books/NBK25501/
[2]: https://pubmed.ncbi.nlm.nih.gov/help/#using-mesh-database
[3]: https://www.ncbi.nlm.nih.gov/books/NBK25498/#chapter3.ELink__ESummaryEfetch
[4]: https://github.com/pmorrell/Plant_Selection/blob/main/pubmed_elink.sh
[5]: https://github.com/pmorrell/Plant_Selection/blob/main/efetch_pmc.sh
