# SafeSpot
## Contributors

|                                       [Samir Gadkari](https://github.com/samirgadkari)               |                                       [Michael Beck](https://github.com/brit228)                              |                                       [Albert Wong](https://github.com/albert-h-wong) |
| :-----------------------------------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------------------------: | :-----------------------------------------------------------------------------------------------------------: |
|                      [<img src="insert src here" width = "200" />](https://github.com/)           |                      [<img src="insert src here" width = "200" />](https://github.com/)                |                      [<img src="insert src here" width = "200" />](https://github.com/) |
|                 [<img src="https://github.com/favicon.ico" width="15"> ](https://github.com/samirgadkari)     |            [<img src="https://github.com/favicon.ico" width="15"> ](https://github.com/brit228)      |           [<img src="https://github.com/favicon.ico" width="15"> ](https://github.com/albert-h-wong) |
| [ <img src="https://static.licdn.com/sc/h/al2o9zrvru7aqj8e1x2rzsrca" width="15"> ](https://www.linkedin.com/in/1samir) | [ <img src="https://static.licdn.com/sc/h/al2o9zrvru7aqj8e1x2rzsrca" width="15"> ](https://www.linkedin.com/in/michaelpbeck) | [ <img src="https://static.licdn.com/sc/h/al2o9zrvru7aqj8e1x2rzsrca" width="15"> ](https://www.linkedin.com/in/albert-wong-53b49a23/) |


SafeSpot provides predictions of crime within a city for a full year from today. You can see crime trends for the last 18 years. You can also select a block of the city on the map and see crime trends for that block. Predictions per block are also shown.

![Scikit-Learn](https://scikit-learn.org/stable/_static/scikit-learn-logo-small.png)
![Keras](https://s3.amazonaws.com/keras.io/img/keras-logo-2018-large-1200.png)
![Pandas](https://pandas.pydata.org/_static/pandas_logo.png)
![Numpy](https://www.numpy.org/_static/numpy_logo.png)


![Deployed App](https://safespot.netlify.com/map)


[Chicago predictions](https://github.com/labs12-crime-statistics/DS/blob/samir-gadkari/Chicago_predictions_combo.ipynb)
[Prophet Model](https://github.com/labs12-crime-statistics/DS/blob/master/Chicago_Prophet_AW.ipynb)
[ARIMA Model](https://github.com/labs12-crime-statistics/DS/blob/master/Chicago_ARIMA.ipynb)
[Other Models](https://github.com/labs12-crime-statistics/DS/blob/master/Chicago_AW1.ipynb)
[Processing raw data](https://github.com/labs12-crime-statistics/DS/blob/master/Chicago.ipynb)



We have data for each reported crime within Chicago (Latitude/Longitude, BlockID, type of crime, location of crime, severity of crime). We model this data to create predictions for the number of crimes each Block would see from now till a year into the future.

Our training set is the last two years of data. Our testing set is data for the next year. We wanted to predict crime counts for each day-of-the-week-hour for each month for each BlockID. The averaging over each day of the week and hour was necessary because most of the hours of the day would have no crime. This caused most of the values in our dataset to be zero, and our model had to fit to those zero values. This would cause the model to fit nothing but zeros, since fitting any higher value would cause errors across all the zeros. This would cause us to predict that most of the blocks of Chicago are safe. We wanted to be conservative in that estimate, and so had to average our values to get more non-zero values.


## Tech Stack

Python, Scikit-Learn, Pandas, Numpy, Keras

## Predictions

To predict with data that had less zeros:
- we averaged the data for each day of the week for each month and each BlockID. When we modeled this data, we got the Day-of-week model.
- we averaged the data for each day of the month for each moth and each BlockID. The model for this data is the Day-of-month model.
- we averaged the data for each hour of the day for each month and each BlockID. The model for this data is the Hour-of-day model.
We wanted to predict for each day-of-week-hour, for each month and each BlockID. To do this we found the values for each data point from each model, and weighed them to get our combined value. Higher weight was given to the values from the model that fit that particular value best.

## Explanatory Variables

-   BlockID: Census counts gave us population per Census tract. Each Census tract became our Block. Each block has a BlockID given by the Census bureau. All crime counts were divided by the population of the block to get a normalized values. This allowed us to remove the fact that larger populations would have higher crime rates.
-   Month: Each month of the year was treated separately to enable the model to find month-to-month patterns.
-   Day-of-week: Crime counts were averaged for each day of the week to enable the model to find patterns across the days.
-   Hour-of-day: Crime counts averaged over each hour enabled the model to find patterns across hours.
-   Explanatory Variable 5

## Data Sources

-   [Chicago Data Portal](https://data.cityofchicago.org/Public-Safety/Crimes-2001-to-present/ijzp-q8t2)
-   [Data.gov](https://catalog.data.gov/dataset/boundaries-census-blocks-2010)
-   [Chicago Police Department](https://data.cityofchicago.org/widgets/c7ck-438e)

## How to connect to the web API

To access the webpage, you can go to [SafeSpot](https://safespot.netlify.com/map).
We do not connect to other services through APIs.

## How to connect to the data API

Our data is loaded onto a PostgreSQL server on AWS. To access it you need the requisite PostgreSQL URL. You can then access it through SQL queries.

## Contributing

When contributing to this repository, please first discuss the change you wish to make via issue, email, or any other method with the owners of this repository before making a change.

Please note we have a [code of conduct](./CODE_OF_CONDUCT.md). Please follow it in all your interactions with the project.

### Issue/Bug Request

    * If you are having an issue with the existing project code, please submit a bug report under the following guidelines:
    * Check first to see if your issue has already been reported.
    * Check to see if the issue has recently been fixed by attempting to reproduce the issue using the latest master branch in the repository.
    * Create a live example of the problem.
    * Submit a detailed bug report including your environment & browser, steps to reproduce the issue, actual and expected outcomes,  where you believe the issue is originating from, and any potential solutions you have considered.

### Feature Requests

We would love to hear from you about new features which would improve this app and further the aims of our project. Please provide as much detail and information as possible to show us why you think your new feature should be implemented.

### Pull Requests

If you have developed a patch, bug fix, or new feature that would improve this app, please submit a pull request. It is best to communicate your ideas with the developers first before investing a great deal of time into a pull request to ensure that it will mesh smoothly with the project.

Remember that this project is licensed under the MIT license, and by submitting a pull request, you agree that your work will be, too.

#### Pull Request Guidelines

    * Ensure any install or build dependencies are removed before the end of the layer when doing a build.
    * Update the README.md with details of changes to the interface, including new plist variables, exposed ports, useful file locations and container parameters.
    * Ensure that your code conforms to our existing code conventions and test coverage.
    * Include the relevant issue number, if applicable.
    * You may merge the Pull Request in once you have the sign-off of two other developers, or if you do not have permission to do that, you may request the second reviewer to merge it for you.

### Attribution

These contribution guidelines have been adapted from [this good-Contributing.md-template](https://gist.github.com/PurpleBooth/b24679402957c63ec426).

See [Backend Documentation](https://github.com/labs12-crime-statistics/Backend) for details on the backend of our project.
