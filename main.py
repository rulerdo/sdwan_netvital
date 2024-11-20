import urllib3
import csv
import os
from catalystwan.session import create_manager_session
import gradio as gr
import pandas as pd


def get_device_health_from_live_vmanage(session, headers):

    try:

        response = session.get("/dataservice/health/devices?page_size=12000")
        devices = response.json()["devices"]
        all_devices = [[device.get(header) for header in headers] for device in devices]
        devices_table = [device for device in all_devices if device[3] == "reachable"]

    except Exception as e:
        raise gr.Error(f"Error: {e}")

    return devices_table


def validate_vmanage_version(session):

    supported = False

    try:

        response = session.get("/dataservice/client/about")
        version = response.json()["data"]["version"]
        major = version.split(".")[0]
        minor = version.split(".")[1]
        gr.Info(f"vManage version: {version}")

        if major != "20" or int(minor) < 9:

            gr.Warning(f"Unsupported vManage version - Min 20.9+")

        else:
            supported = True

    except Exception as e:
        raise gr.Error(f"Error: {e}")

    return supported


def filter_devices_from_health_table(filter, devices_table):

    controllers = ["vsmart", "vbond", "vmanage"]

    try:

        if filter == "controllers":
            filtered_health_table = [row for row in devices_table if row[2] in controllers]
        elif filter == "edges":
            filtered_health_table = [row for row in devices_table if row[2] == "vedge"]
        else:
            raise gr.Error(f"Unsupported device type {filter}")

    except Exception as e:
        raise gr.Error(f"Error: {e}")

    return filtered_health_table


def save_data_to_csv(destination_file, headers, data_table):

    try:

        with open(destination_file, "w") as f:
            csv_writer = csv.writer(f)
            csv_writer.writerow(headers)
            csv_writer.writerows(data_table)

    except Exception as e:
        raise gr.Error(f"Error: {e}")


def sort_table_by_index_desc(table, index, n=10):

    try:

        sorted_table = sorted(table, key=lambda x: x[index], reverse=True)
        top_ten = sorted_table[:n]

    except Exception as e:
        raise gr.Error(f"Error: {e}")

    return top_ten


def run(url, username, password, port, customer):

    with create_manager_session(
        url=url,
        username=username,
        password=password,
        port=int(port),
    ) as session:

        supported = validate_vmanage_version(session)

        if not supported:

            return None, None, None, None

        headers = [
            "name",
            "system_ip",
            "device_type",
            "reachability",
            "software_version",
            "health",
            "qoe",
            "cpu_load",
            "memory_utilization",
        ]

        devices_table = get_device_health_from_live_vmanage(session, headers)

    report_filename = f"{customer}_all_devices_health_report.csv"
    save_data_to_csv(report_filename, headers, devices_table)
    controllers_health_table = filter_devices_from_health_table("controllers", devices_table)
    edge_health_table = filter_devices_from_health_table("edges", devices_table)
    top_ten_edges_high_cpu = sort_table_by_index_desc(edge_health_table, 7, n=10)
    top_ten_edges_high_mem = sort_table_by_index_desc(edge_health_table, 8, n=10)
    controllers_df = pd.DataFrame(controllers_health_table, columns=headers)
    edges_cpu_df = pd.DataFrame(top_ten_edges_high_cpu, columns=headers)
    edges_mem_df = pd.DataFrame(top_ten_edges_high_mem, columns=headers)
    gr.Info(f"All tasks completed!")

    return controllers_df, edges_cpu_df, edges_mem_df, report_filename


if __name__ == "__main__":

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    with gr.Blocks(title="Cisco SD-WAN NetVital Stats") as demo:

        with gr.Row():
            with gr.Column():
                with gr.Tab("Inputs"):
                    vmanage = gr.Textbox(
                        label="vManage Host: ",
                        value=os.getenv("VMANAGE_IP", "")
                    )
                    username = gr.Textbox(
                        label="Username: ",
                        value=os.getenv("VMANAGE_USER", "")
                    )
                    password = gr.Textbox(
                        label="Password: ",
                        type="password",
                        value=os.getenv("VMANAGE_PASSWORD", ""),
                    )
                    port = gr.Textbox(
                        label="Port: ",
                        value=os.getenv("VMANAGE_PORT", "")
                    )
                    customer = gr.Textbox(
                        label="Customer Name: ",
                        value=os.getenv("CUSTOMER_NAME", "")
                    )
                    submit_button = gr.Button("Submit")

        with gr.Row():
            with gr.Column():
                with gr.Tab("Outputs"):
                    controllers_out = gr.DataFrame(label="Controllers Health")
                    high_cpu_out = gr.DataFrame(label="Top10 Edges High CPU")
                    high_memory_out = gr.DataFrame(label="Top10 Edges High Memory")
                    csv_report_out = gr.File(label="CSV Report - All devices")

        submit_button.click(
            fn=run,
            inputs=[
                vmanage,
                username,
                password,
                port,
                customer,
            ],
            outputs=[
                controllers_out,
                high_cpu_out,
                high_memory_out,
                csv_report_out,
            ],
        )

    demo.launch(show_error=True)
