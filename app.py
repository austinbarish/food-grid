# Imports
import pandas as pd
import numpy as np
import requests
import json
import time
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns
from shiny import render, ui, App, reactive
from shinywidgets import output_widget, render_widget
import shinyswatch
from ast import literal_eval
from sklearn.preprocessing import MinMaxScaler
import math

# Import Data
df = pd.read_csv(
    "https://raw.githubusercontent.com/austinbarish/food-grid/main/data/dc_reviews_cleaned.csv",
    index_col=0,
    converters={"categories": literal_eval},
)

# Create Color Map
# Done outside the function to remain consistent
# Create a color palette with as many colors as there are categories
custom_palette = sns.color_palette("husl", len(df.main_category.unique())).as_hex()
color_map = {cat: custom_palette[i] for i, cat in enumerate(df.main_category.unique())}


# Create a dict of all the categories
categories = {cat: cat for cat in df.categories.explode().unique()}

# Create a dict of all the main categories
main_categories = {cat: cat for cat in df.main_category.unique()}

# Add an "All" option to the categories
categories["All Categories"] = "All Categories"
main_categories["All Categories"] = "All Categories"

# Get all restaurants
restaurants = df.name.unique()

# Create a dict of restaurants
restaurants_dict = {restaurant: restaurant for restaurant in restaurants}


# App UI
app_ui = ui.page_fluid(
    shinyswatch.theme.pulse(),
    ui.tags.head(
        ui.HTML(
            "<script async src='https://www.googletagmanager.com/gtag/js?id=G-7W30E7JTR7'></script><script>window.dataLayer = window.dataLayer || [];function gtag(){dataLayer.push(arguments);}gtag('js', new Date());gtag('config', 'G-7W30E7JTR7');</script>"
        )
    ),
    ui.panel_title(
        "DC Restaurant Grid",
        window_title="DC Restaurant Grid",
    ),
    ui.layout_sidebar(
        ui.sidebar(
            ui.input_slider(
                "rating_range",
                "Rating Range",
                min=0,
                max=100,
                value=[0, 100],
                step=1,
            ),
            ui.input_slider(
                "review_count_range",
                "Review Count Range",
                min=0,
                max=max(df.total_reviews),
                value=[0, max(df.total_reviews)],
                step=1,
            ),
            ui.input_checkbox_group(
                "price",
                "Select Price",
                choices=["$", "$$", "$$$", "$$$$"],
                selected=["$", "$$", "$$$", "$$$$"],
            ),
            ui.input_selectize(
                "main_category",
                "Select Main Category",
                choices=main_categories,
                multiple=True,
                selected="All Categories",
            ),
            ui.input_selectize(
                "restaurant_highlighter",
                "Highlight Restaurant(s)",
                choices=restaurants_dict,
                multiple=True,
            ),
            ui.input_radio_buttons(
                "coloring",
                "Data Coloring:",
                {
                    "category": "By Category",
                    "price": "By Price",
                    "score": "By Total Score",
                },
                selected="category",
            ),
            ui.input_action_button(id="refresh", label="Refresh", class_="btn-success"),
            ui.input_switch(id="dt_switch", label="Show Data Table"),
        ),
        output_widget("grid"),
        ui.panel_conditional(
            "input.dt_switch",
            ui.output_data_frame("data_table"),
        ),
    ),
    ui.panel_well(
        "Created by ",
        ui.a(
            "Austin Barish",
            href="https://github.com/austinbarish",
            target="_blank",
        ),
        ". Check out the code on ",
        ui.a(
            "Github",
            href="https://github.com/austinbarish/food-grid",
            target="_blank",
        ),
        ". Data collected using ",
        ui.a(
            "Google Maps",
            href="https://developers.google.com/maps",
            target="_blank",
        ),
        " and ",
        ui.a(
            "Yelp",
            href="https://www.yelp.com/developers",
            target="_blank",
        ),
        ". Last updated: January 2024.",
    ),
)


# Function that filters data given filters
def data_filterer(
    df,
    rating_range=[0, 100],
    review_range=[0, 100],
    prices=["$", "$$", "$$$", "$$$$"],
    main_category=["All Categories"],
):
    try:
        # Filter the dataframe by rating and review count
        df = df[
            (df.rounded_normalized_rating >= rating_range[0])
            & (df.rounded_normalized_rating <= rating_range[1])
            & (df.total_reviews >= review_range[0])
            & (df.total_reviews <= review_range[1])
        ]

        # Add price codes
        price_map = {"$": 1, "$$": 2, "$$$": 3, "$$$$": 4}
        df["price_code"] = df.price.map(price_map)

        prices_codes = [price_map[price] for price in prices]

        # Filter the dataframe by price
        df = df[df.price_code.isin(prices_codes)]

        if "All Categories" not in main_category and list(main_category) != []:
            df = df[df.main_category.isin(main_category)]

        # Sort by main category so it is alphabetical
        df = df.sort_values(by=["main_category"])

        # Calculate raw score
        df["score"] = (df["normalized_rating"] * 10) * (
            df["normalized_total_reviews"] / 100
        )

        # Apply logarithmic transformation to score
        df["score"] = df["score"].apply(lambda x: 0 if x == 0 else math.log(x + 1))

        # Use MinMaxScaler for normalization
        scaler = MinMaxScaler()
        df["score"] = scaler.fit_transform(df[["score"]]) * 100

        # Round the score
        df["score"] = df["score"].round(2)

    except:
        df = pd.DataFrame()

    return df


def error_plot():
    template = go.layout.Template()
    template.layout.annotations = [
        dict(
            name="draft watermark",
            text="No Restaurants Found<br>Please Try Adjusting Filters",
            opacity=0.4,
            font=dict(color="red", size=50),
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
        )
    ]

    fig = go.Figure()
    fig.update_layout(template=template)
    return fig


# Function to create plot
def create_grid(
    df,
    color_map=color_map,
    rating_range=[0, 100],
    review_range=[0, 100],
    prices=["$", "$$", "$$$", "$$$$"],
    main_category=["All Categories"],
    coloring="category",
    highlighted_restaurants=[],
):
    # Filter the data
    df = data_filterer(
        df,
        rating_range,
        review_range,
        prices,
        main_category,
    )

    # Check to make sure there are restaurants left
    if len(df) == 0:
        return error_plot()

    # Find averages for quadrant lines
    x_avg = df["normalized_rating"].mean()
    y_avg = df["normalized_total_reviews"].mean()

    # Check if highlighted restaurants is empty and if so, give error plot
    if list(highlighted_restaurants) != []:
        try:
            # Create Color Map for Highlighted Restaurants
            df["Highlighted"] = np.where(
                df["name"].isin(highlighted_restaurants), df["name"], "Other"
            )
            highlighted_color_map = {
                name: "highlight" for name in enumerate(df.Highlighted.unique())
            }

            # Set the size for highlighted and non-highlighted datapoints
            highlighted_size = 10
            non_highlighted_size = 2

            df["highlighted_size"] = np.where(
                df["Highlighted"] == "Other", non_highlighted_size, highlighted_size
            )

            # Change Other to Gray
            highlighted_color_map["Other"] = "gray"

        except:
            return error_plot()

        # Create Scatter
        fig = px.scatter(
            df,
            x="normalized_rating",
            y="normalized_total_reviews",
            color="Highlighted",
            color_discrete_map=highlighted_color_map,
            size="highlighted_size",
            size_max=highlighted_size,
            hover_name="name",
            custom_data=[
                "name",
                "price",
                "average_rating",
                "rounded_normalized_rating",
                "total_reviews",
                "url",
                "score",
            ],
            title="DC Restaurant Grid",
            labels={"Highlighted": "Highlighted Restaurants"},
            # text='name'
        )

    # If not highlighted:
    else:
        if coloring == "price":
            # Sort by price to be $, $$, $$$, $$$$
            df = df.sort_values(by=["price"])

            # Get the Greens color scale from Plotly
            greens = px.colors.sequential.Greens

            # Create Color Map for Price
            price_color_map = {
                "$": greens[2],  # Light Green
                "$$": greens[4],  # Medium Green
                "$$$": greens[6],  # Dark Green
                "$$$$": greens[8],  # Darkest Green
            }

            # Create Scatter
            fig = px.scatter(
                df,
                x="normalized_rating",
                y="normalized_total_reviews",
                color="price",
                color_discrete_map=price_color_map,
                hover_name="name",
                custom_data=[
                    "name",
                    "price",
                    "average_rating",
                    "rounded_normalized_rating",
                    "total_reviews",
                    "url",
                    "score",
                ],
                labels={"price": "Price"},
                # text='name'
            )

        elif coloring == "score":
            # Create Scatter
            fig = px.scatter(
                df,
                x="normalized_rating",
                y="normalized_total_reviews",
                color="score",
                color_continuous_scale="RdYlGn",
                hover_name="name",
                custom_data=[
                    "name",
                    "price",
                    "average_rating",
                    "rounded_normalized_rating",
                    "total_reviews",
                    "url",
                    "score",
                ],
                labels={
                    "score": "<b>Score</b> <br>Normalized Log of Normalized Review Count * Normalized Rating"
                },
                # text='name'
            )

            # Move colorbar to the right
            fig.update_layout(coloraxis_colorbar=dict(title_side="right"))

        else:
            # Create Scatter
            fig = px.scatter(
                df,
                x="normalized_rating",
                y="normalized_total_reviews",
                color="main_category",
                color_discrete_map=color_map,
                hover_name="name",
                custom_data=[
                    "name",
                    "price",
                    "average_rating",
                    "rounded_normalized_rating",
                    "total_reviews",
                    "url",
                    "score",
                ],
                # text='name'
            )

    # Update the hover template to include only 'name' and 'price'
    fig.update_traces(
        hovertemplate="<b><a href='%{customdata[5]}' style='text-decoration: underline; color: inherit;'>%{hovertext}</a></b><br>Price: %{customdata[1]}<br>Rating: %{customdata[2]:.2f}<br>Normalized Rating: %{customdata[3]}<br>Review Count: %{customdata[4]:,}<br>Score: %{customdata[6]:.2f}"
    )
    fig.update_layout(hovermode="closest", hoverdistance=10000)

    # Add quadrant lines and text if there are enough restaurants
    if len(df) > 4:
        # Add quadrant Lines
        fig.add_vline(x=x_avg, line_width=1, opacity=0.5)
        fig.add_hline(y=y_avg, line_width=1, opacity=0.5)

        # If there are restaurant above and below a 50 on both x axis, include the text
        if min(df["normalized_rating"]) < 50 and max(df["normalized_rating"]) > 50:
            # Find midpoints for quadrants
            # Not actual 75th and 25th percentiles; modified for better visualization
            x_75 = (
                np.mean(df["normalized_rating"])
                + (max(df["normalized_rating"]) - np.mean(df["normalized_rating"])) / 2
            )
            if (
                min(df["normalized_rating"]) == 0
                and np.mean(df["normalized_rating"]) > 25
            ):
                x_25 = 20
            else:
                x_25 = (
                    np.mean(df["normalized_rating"]) - min(df["normalized_rating"])
                ) / 2
            y_75 = (
                np.mean(df["normalized_total_reviews"])
                + (
                    max(df["normalized_total_reviews"])
                    - np.mean(df["normalized_total_reviews"])
                )
                / 2
            )
            y_25 = min(df["normalized_total_reviews"])

            # Add quadrant text
            fig.add_annotation(
                x=x_75, y=y_75, text="Deservedly Popular", showarrow=False
            )
            fig.add_annotation(x=x_75, y=y_25, text="Hidden Gems", showarrow=False)
            fig.add_annotation(x=x_25, y=y_75, text="Overrated", showarrow=False)
            fig.add_annotation(x=x_25, y=y_25, text="Not Worth It", showarrow=False)

    # Clean
    fig.update_layout(
        template="plotly",
        xaxis_title="<b>Normalized Rating</b>",
        yaxis_title="<b>Popularity Score</b>  <br>Normalized Review Count",
        height=700,
        width=1000,
    )

    # Return the plot
    return fig


# Create Server
def server(input, output, session):
    # Create a server object
    server = type("Server", (), {})()

    # Create Plot
    @render_widget
    @reactive.event(input.refresh, ignore_none=False)
    def grid():
        # Create the plot
        fig = create_grid(
            df,
            color_map=color_map,
            rating_range=input.rating_range(),
            review_range=input.review_count_range(),
            prices=input.price(),
            main_category=input.main_category(),
            highlighted_restaurants=input.restaurant_highlighter(),
            coloring=input.coloring(),
        )
        return fig

    # Create Data Table
    @render.data_frame
    @reactive.event(input.refresh, ignore_none=False)
    def data_table():
        # Filter the data
        df_filtered = data_filterer(
            df,
            rating_range=input.rating_range(),
            review_range=input.review_count_range(),
            prices=input.price(),
            main_category=input.main_category(),
            # categories=input.categories(),
        )

        # Only include highlighted restaurants if they are selected
        if list(input.restaurant_highlighter()) != []:
            df_filtered = df_filtered[
                df_filtered.name.isin(input.restaurant_highlighter())
            ]

        # Select Columns
        df_filtered = df_filtered[
            [
                "name",
                "main_category",
                "categories",
                "price",
                "average_rating",
                "rounded_normalized_rating",
                "total_reviews",
                "rounded_normalized_total_reviews",
                "score",
            ]
        ]

        # Round average rating to 3 decimal places
        df_filtered["average_rating"] = df_filtered["average_rating"].round(3)

        # Remove underscores
        df_filtered.columns = [col.replace("_", " ") for col in df_filtered.columns]

        # Capitalize Column names
        df_filtered.columns = [col.title() for col in df_filtered.columns]

        # Remove the word "Rounded"
        df_filtered.columns = [
            col.replace("Rounded ", "") for col in df_filtered.columns
        ]

        # Add space between commas in categories
        df_filtered["Categories"] = df_filtered["Categories"].str.join(", ")

        # Sort by normalized rating, normalized review count
        df_filtered = df_filtered.sort_values(
            by=["Normalized Rating", "Normalized Total Reviews"], ascending=False
        )

        return df_filtered


# Create the app
app = App(app_ui, server)
