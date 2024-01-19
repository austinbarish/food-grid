# Imports
import pandas as pd
import numpy as np
import requests
import json
import time
import plotly.express as px
import plotly.graph_objects as go
from shiny import render, ui, App, reactive
from shinywidgets import output_widget, render_widget
import shinyswatch
from ast import literal_eval

# Import Data
df = pd.read_csv(
    "https://raw.githubusercontent.com/austinbarish/food-grid/main/data/dc_reviews_cleaned.csv",
    index_col=0,
    converters={"categories": literal_eval},
)

# Create Color Map
# Done outside the function to remain consistent
colors = px.colors.qualitative.Light24
color_map = {cat: colors[i] for i, cat in enumerate(df.main_category.unique())}

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
    shinyswatch.theme.cerulean(),
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
            # ui.input_selectize(
            #     "categories",
            #     "Select Categories",
            #     choices=categories,
            #     multiple=True,
            #     selected="All Categories",
            # ),
            ui.input_selectize(
                "restaurant_highlighter",
                "Highlight Restaurant(s)",
                choices=restaurants_dict,
                multiple=True,
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
    # categories=["All Categories"],
):
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

    if "All Categories" not in main_category:
        df = df[df.main_category.isin(main_category)]

    return df


# Function to create plot
def create_grid(
    df,
    color_map=color_map,
    rating_range=[0, 100],
    review_range=[0, 100],
    prices=["$", "$$", "$$$", "$$$$"],
    main_category=["All Categories"],
    # categories=["All Categories"],
    highlighted_restaurants=[],
):
    # Filter the data
    df = data_filterer(
        df,
        rating_range,
        review_range,
        prices,
        main_category,
        # categories=input.categories(),
    )

    # Check to make sure there are restaurants left
    if len(df) == 0:
        draft_template = go.layout.Template()
        draft_template.layout.annotations = [
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
        fig.update_layout(template=draft_template)
        return fig

    # Find averages for quadrant lines
    x_avg = df["normalized_rating"].mean()
    y_avg = df["normalized_total_reviews"].mean()

    # Check if highlighted restaurants is empty
    if list(highlighted_restaurants) != []:
        # Create Color Map for Highlighted Restaurants
        df["Highlighted"] = [
            name if name in highlighted_restaurants else "Other" for name in df.name
        ]
        highlighted_color_map = {
            name: "red" for name in enumerate(df.Highlighted.unique())
        }

        # Change Other to Gray
        highlighted_color_map["Other"] = "gray"

        # Create Scatter
        fig = px.scatter(
            df,
            x="normalized_rating",
            y="normalized_total_reviews",
            color="Highlighted",
            color_discrete_map=highlighted_color_map,
            hover_name="name",
            custom_data=[
                "name",
                "price",
                "average_rating",
                "rounded_normalized_rating",
                "total_reviews",
            ],
            title="DC Restaurant Grid",
            labels={"main_category": "Category"},
            # text='name'
        )
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
            ],
            labels={"main_category": "Category"},
            # text='name'
        )

    # Update the hover template to include only 'name' and 'price'
    fig.update_traces(
        hovertemplate="<b><a href='%{customdata[5]}' style='text-decoration: underline; color: inherit;'>%{hovertext}</a></b><br>Price: %{customdata[1]}<br>Rating: %{customdata[2]:.2f}<br>Normalized Rating: %{customdata[3]}<br>Review Count: %{customdata[4]:,}"
    )

    # Add quadrant Lines
    fig.add_vline(x=x_avg, line_width=1, opacity=0.5)
    fig.add_hline(y=y_avg, line_width=1, opacity=0.5)

    # category_options = [
    #     {
    #         "label": "All Restaurants",
    #         "method": "update",
    #         "args": [
    #             {"visible": [True] * len(df)},
    #             {"title.text": "DC Restaurant Grid - All Restaurants"},
    #         ],
    #     }
    # ]

    # if categories != ["All Categories"]:
    #     for category in categories:
    #         category_bools = df["main_category"] == category
    #         category_options += [
    #             {
    #                 "label": category,
    #                 "method": "update",
    #                 "args": [
    #                     {"visible": category_bools},
    #                     {"title.text": f"DC Restaurant Grid - Category: {category}"},
    #                 ],
    #             }
    #         ]

    # Find midpoints for quadrants
    x_75 = max(df["normalized_rating"]) * 0.9
    x_25 = min(df["normalized_rating"]) * 1.1
    y_75 = max(df["normalized_total_reviews"]) * 0.9
    y_25 = min(df["normalized_total_reviews"]) * 1.1

    # Add quadrant text
    fig.add_annotation(x=x_75, y=y_75, text="Deservedly Popular", showarrow=False)
    fig.add_annotation(x=x_75, y=y_25, text="Hidden Gems", showarrow=False)
    fig.add_annotation(x=x_25, y=y_75, text="Overrated", showarrow=False)
    fig.add_annotation(x=x_25, y=y_25, text="Not Worth It", showarrow=False)

    # Clean
    fig.update_layout(
        template="plotly_white",
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
            # categories=input.categories(),
            highlighted_restaurants=input.restaurant_highlighter(),
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
            ]
        ]

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
