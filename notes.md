# Plant_selection
Code for identifying features of the plant resequencing literature

## Step 01
We are performing a literature search for all papers related to whole genome population
genetic studies of plants. 


journal article[pt]
AND (
      plant[tiab] OR plants[tiab]
   OR crop[tiab] OR crops[tiab]
   OR "crop plant"[tiab] OR "crop species"[tiab]
   OR domestication[tiab] OR "domesticated plant"[tiab]
)
AND (
      resequenc*
   OR "re-sequenc*"
   OR "whole-genome sequenc*"
   OR "whole genome sequenc*"
)
AND (
      "balancing selection"[tiab]
   OR "hard sweep"[tiab]
   OR "negative selection"[tiab]
   OR "polygenic selection"[tiab]
   OR "positive selection"[tiab]
   OR "purifying selection"[tiab]
   OR "selective sweep"[tiab]
   OR "soft sweep"[tiab]
   OR "selection coefficient"[tiab]
   OR "adaptive introgression"[tiab]
   OR selection[tiab]
)
NOT Animals[MeSH Terms]
NOT Humans[MeSH Terms]
NOT Vertebrates[MeSH Terms]
NOT (
      assembly[tiab]
   OR "genome assembly"[tiab]
   OR "de novo"[tiab]
   OR review[pt]
   OR editorial[pt]
   OR comment[pt]
)


