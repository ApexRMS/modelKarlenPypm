# modelKarlenPypm

*modelKarlenPypm* add-on package (to epi) for estimating parameters and making regional projections of COVID-19 spread. 

It uses the discrete-time modelling framework [pypmca](https://pypm.github.io/home/) (Github [here](https://github.com/pypm/pypmca)) for interconnecting populations. *pypmca* is coded in Python, and various pre-tuned regional scenarios can be downloaded from the [pypmca Github](https://github.com/pypm/pypmca). In *modelKarlenPypm*, a desired pre-tuned scenario object (titled *<region_name>-<date/version>.pypm*) is downloaded; it contains all the modelling parameters, populations, delays, connectors, etc implemented by [Prof Dean Karlen (UVic)](https://www.uvic.ca/science/physics/vispa/people/faculty/karlen.php).
