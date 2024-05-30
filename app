# Import necessary libraries
from dash import Dash, dcc, html, Input, Output
import plotly.express as px
import pandas as pd
from jupyter_dash import JupyterDash

# Sample Data
df = pd.DataFrame({
    "Date": pd.date_range(start="2023-01-01", periods=100),
    "Value": range(100)
})

# Create a Dash app
app = JupyterDash(__name__)

# Layout of the Dashboard
app.layout = html.Div([
    html.H1("Simple Dashboard"),
    dcc.Graph(id='line-chart'),
    dcc.Slider(
        id='slider',
        min=df['Value'].min(),
        max=df['Value'].max(),
        value=df['Value'].max(),
        marks={str(i): str(i) for i in range(df['Value'].min(), df['Value'].max()+1, 10)},
        step=1
    )
])

# Callback to update the graph
@app.callback(
    Output('line-chart', 'figure'),
    [Input('slider', 'value')]
)
def update_figure(selected_value):
    filtered_df = df[df['Value'] <= selected_value]
    fig = px.line(filtered_df, x='Date', y='Value', title='Line Chart')
    return fig

# Function to run the Dash app
def run_dash_app():
    app.run_server(host='JSWSL-DOL-D3168', port=8052, debug=True)

# Run the Dash app
run_dash_app()
