# DS
**Contributors**

* [Samir Gadkari](https://github.com/samirgadkari)
* [Albert Wong](http://github.com/albert-h-wong)
* [Michael Beck](http://github.com/brit228)

[Link to trello board](https://trello.com/b/VX0UcKdA/labs*12-crime-statistics)


## Predictions
Our dataset does not have locations/times where crime was *not* committed.
If we give the dataset as-is to a neural network, it *has* to give us a
crime back. It does not have the option of saying "there was no crime."


We give the user the ability to specify the day/time in which they're interested.
For each hour since the first crime date in our dataset:
  * If there were crimes committed, there will be one or more rows of data with:
      * IUCR code (fully describing the type/description of crime)
      * severity of the crime (this is a value created from the IUCR).
      This severity is normalized with the population of the tract that the
      crime was committed in.
      One other possibility that was considered was to normalize the severity
      for each crime type/description. Since there are ~9000 of those combinations
      of crime type/description, it will be too many columns per crime. Also, the
      severity is already taking into account the crime type/description.
  * If there were no crimes committed during that hour,
    we say "no crime was committed" by specifying:
    * IUCR code of 0
    * severity of 0


We will predict the severity of crimes and then find the risk rating using:
  * risk rating = SUM(severity) / SUM(population)
### Predicting risk rating of tract
For each hour since the earliest data in our dataset:
  * Group all crimes in each tract
  * Find the average severity of crimes in each tract


Feed these values to the neural network:
  * Date
  * Hour of day
  * tract number
  * average severity of crime in each tract
    * If there was no crime committed, the average severity will be 0


We predict the severity of the crime for each date/hour/tract for the next year.
Given the severity, we normalize it with the population of the tract
to get a risk rating.


Our data starts from 01/01/2001. We have 24 * 365 * 17 (~ 150000)
hours of data as our training set. There are 866 census tracts in Chicago.
We then have 150000 * 866 = 130 million data points.
We will have to see how many hours in all tracts are crime-free.
If there is a large imbalance, we will undersample the 'no crime' class
or oversample the 'crime committed' class to get a good prediction.
From research, a ratio of 1:2 of crime to 'no crime' has been found
to work well. We will use this ratio in our sampling.
### Predicting location and type/description of crime
This is a more involved prediction.  Since we're predicting the location
of the crime as well, we have to:
  * Create a grid of points over Chicago (of size a few blocks square)
  * Map the current crimes to those locations (based on Euclidean distance,
  since our points will not be at the corner of each block)


This will create much more data to feed the neural network. The whole grid
for the city of Chicago worth of locations will be given values for each
hour of the day since the earliest day in our dataset.


Our data starts from 01/01/2001. We have 24 * 365 * 17 (~ 150000)
hours of data as our training set. The City of Chicago is 227 square miles *
that is approximately 15 miles square. Each mile contains 8 city blocks,
so 120 x 120 square blocks = 14400 blocks in the city. If we have a point
per block, the total number of points we have to feed our neural network
becomes 14400 x 150000 = 2 billion. Most of these points will not have
crimes committed, so we will have to downsample the majority class ("no crime").
Still, it looks like a daunting task to go through such a large set of points
to train a neural net.


The result of this training will be predicting the IUCR code (which is the same
as type/description) and the location of the crime. We can convert this to severity/location.
What we're displaying to the user though, is a color per tract. So we will have to
averge all the severity values for each location in each tract. This is probably overkill, 
since we're not really using the individual location information.


* Feed this data into the Neural Network for training:
    * Grid point location
    * Date and each hour
    * Type/description of crime (IUCR value from the dataset fully describes this)
    * severity of crime
