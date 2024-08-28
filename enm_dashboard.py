import os
import sys
import requests
import re
from collections import OrderedDict
from http import HTTPStatus
from bs4 import BeautifulSoup

AUTH = {'Authorization':
        'Basic VEtKQVdBSEZCSjpmQCU2ZTRLMzI5cXdYb2tabHJjY2tyRzl3'}

DROP_URL = "https://pdu-oss-tools4.seli.wh.rnd.internal.ericsson.com/" +\
           "cenm_dashboard/api/data/getENMDrop"
CENM_URL = "https://pdu-oss-tools4.seli.wh.rnd.internal.ericsson.com/" +\
           "cenm_dashboard/api/data/getData"
PUBLISH_URL = "https://fem16s11-eiffel004.eiffel.gic.ericsson.se:8443/" +\
              "jenkins/job/eric-enm-sdk-publish/"
BUILDMANAGER_URL = "https://fem16s11-eiffel004.eiffel.gic.ericsson.se:8443/" +\
                   "jenkins/job/sdk-csar-buildmanager/"
DASHBOARD_URL = "https://pdu-oss-tools4.seli.wh.rnd.internal.ericsson.com/" +\
                "cenm_dashboard/#dashboard"
PRODUCT_SET_URL = "https://ci-portal.seli.wh.rnd.internal.ericsson.com/" +\
                  "cloudnative/getCloudNativeProductSetContent"
CONFLUENCE_URL = "https://confluence-oss.seli.wh.rnd.internal.ericsson.com/" +\
                 "rest/api/content/550398751"
FM_TEMPLATES_URL = "https://fem16s11-eiffel004.eiffel.gic.ericsson.se:8443/" +\
                "jenkins/job/fm-sdk-templates/"
PM_TEMPLATES_URL = "https://fem16s11-eiffel004.eiffel.gic.ericsson.se:8443/" +\
                   "jenkins/job/pm-sdk-templates/"
FM_TEMPLATES_NEXUS = "https://arm2s11-eiffel004.eiffel.gic.ericsson.se:8443/" +\
                     "nexus/content/repositories/cloud-native-enm-sdk/" +\
                     "templates/releases/fm-sdk-templates/"
PM_TEMPLATES_NEXUS = "https://arm2s11-eiffel004.eiffel.gic.ericsson.se:8443/" +\
                     "nexus/content/repositories/cloud-native-enm-sdk/" +\
                     "templates/releases/pm-sdk-templates/"
HISTORY_URL = "https://confluence-oss.seli.wh.rnd.internal.ericsson.com/" +\
                 "rest/api/content/570356740"
CENM_TEMPLATE = "https://ci-portal.seli.wh.rnd.internal.ericsson.com/" \
                "cloudnative/getCloudNativeProductSetContent/l{}/{}"
SDK_TEMPLATES = "https://arm2s11-eiffel004.eiffel.gic.ericsson.se:8443/nexus/" \
                "content/repositories/cloud-native-enm-sdk/buildmanager/" \
                "buildmanager-csar/cloud-native-enm-sdk/{}"

chart_param = os.environ.get('SDK_CHART_VERSION')
product_set_param = os.environ.get('PRODUCT_SET_VERSION')

GREEN, RED, YELLOW, BLACK = "#89BA17", "#E32119", "#D6BC02", "#333333"

template = """
<ul class="tab-list">
  <li style="font-family: 'Ericsson Hilda', 
  Helvetica, Arial, sans-serif; padding: 10px; 
  color: white; text-align: center;">
  <a href="#tab1" class="active">Dashboard</a></li>
  {tabs}
</ul>

<div id="tab1" class="tab-content active">
  {dashboard_html}
</div>

{tabs_content}

<style>
  .tab-list {{
    list-style: none !important;
    margin: 0;
    padding: 0;
    overflow: hidden;
    background-color: #f1f1f1;
    display: flex;
  }}

  .tab-list li a {{
    display: block;
    color: black;
    text-align: center;
    padding: 14px 16px;
    text-decoration: none;
    transition: 0.3s;
  }}

  .tab-list li a:hover {{
    background-color: #ddd;
  }}

  .tab-list li a.active {{
    background-color: #ccc;
  }}

  .tab-content {{
    display: none;
    padding: 6px 12px;
    border: 1px solid #ccc;
    border-top: none;
  }}

  .tab-content.active {{
    display: block;
  }}
</style>

<script>
  const tabLinks = document.querySelectorAll('.tab-list li a');

  tabLinks.forEach(tabLink => {{
    tabLink.addEventListener('click', e => {{
      e.preventDefault();

      tabLinks.forEach(link => {{
        link.classList.remove('active');
      }});

      tabLink.classList.add('active');

      const tabContent = document.querySelectorAll('.tab-content');
      tabContent.forEach(content => {{
        content.classList.remove('active');
      }});

      const target = tabLink.getAttribute('href');
      const tabToShow = document.querySelector(target);
      tabToShow.classList.add('active');
    }});
  }});

  tabLinks[0].classList.add('active');
  const firstTabContent = document.querySelector('#tab1');
  firstTabContent.classList.add('active');
</script>
"""


def _get(url, authentication, json):
    try:
        response = requests.get(url, headers=authentication)
        if HTTPStatus.OK == response.status_code:
            if json:
                return response.json()
            else:
                return response.text
        else:
            raise ValueError(f'Critical error (GET {url}): '
                             f'{response.status_code}')
    except ValueError as err:
        print(err)
        sys.exit()


def _get_non_critical(url, authentication):
    try:
        response = requests.get(url, headers=authentication)
        if HTTPStatus.OK == response.status_code:
            return response.text
        else:
            raise ValueError(f'Controlled error '
                             f'(GET {url}): '
                             f'{response.status_code}')
    except ValueError as err:
        print(err)


def _post(url, authentication, data):
    try:
        response = requests.put(url,
                                headers=authentication, json=data)
        if HTTPStatus.OK == response.status_code:
            print("Dashboard successfully updated")
        else:
            raise ValueError(f'Critical error (POST {url}): '
                             f'{response.status_code}')
    except ValueError as err:
        print(err)
        sys.exit()


def merge_arrays(keys, values):
    merged_list = OrderedDict()
    for i in range(len(keys)):
        merged_list[keys[i]] = values[i]
    return merged_list


def get_status_and_version(data):
    count = 0
    statuses = []
    versions = []
    for i, _ in enumerate(data):
        if data[i]["manualStatus"] == "Green":
            statuses.append("passed")
            versions.append(data[i]["cenm_product_set_version"])
            count += 1
        if data[i]["manualStatus"] == "Red":
            statuses.append("failed")
            count += 1
            versions.append(data[i]["cenm_product_set_version"])
        if data[i]["manualStatus"] == "Yellow":
            statuses.append("waiting")
            count += 1
            versions.append(data[i]["cenm_product_set_version"])
    return statuses, versions


def get_drop(url, authentication):
    _data = _get(url, authentication, True)
    return _data["drop"]


def get_cenm_dashboard(url, authentication):
    _data = _get(url, authentication, True)
    return get_status_and_version(_data)


def get_builds(url, authentication):
    job_url = url + "api/json?pretty=true"
    _data = _get(job_url, authentication, True)

    build_numbers = []
    results = []
    corresponding_product_set = []
    current_product_set = ""
    for item in _data['builds']:
        if current_product_set not in versions and current_product_set != "":
            break
        build_number = item['number']
        build_url = url + str(build_number) + "/api/json?pretty=true"
        build_numbers.append(build_number)

        _data = _get(build_url, authentication, True)

        result = _data['result']
        if result == "FAILURE":
            result = "failed"
        if result == "SUCCESS":
            result = "passed"
        if result == "null":
            result = "building"
        parameters_index = 0
        for index, _ in enumerate(_data["actions"]):
            if "parameters" in _data["actions"][index]:
                parameters_index = index
                break
        product_set_version = _data['actions'][parameters_index][
            'parameters'][2]['value']
        if product_set_version in versions:
            results.append(result)
            corresponding_product_set.append(product_set_version)
        current_product_set = product_set_version
    return build_numbers, results, corresponding_product_set, \
        current_product_set


def get_versions(arr, url1, url2, authentication, job_name):
    results = arr
    job_url = url1 + "api/json?pretty=true"
    _data = _get(job_url, authentication, True)

    chart_versions = []
    count = 0
    skip = False
    if not results[0]:
        chart_versions.append(". . .")
        count += 1
        skip = True

    for item in _data['builds']:
        if skip:
            skip = False
            continue
        count += 1

        if count > len(results):
            break
        build_number = item['number']
        console_text_url = url1 + str(build_number) + "/consoleText"
        job_number = ""
        _text = _get(console_text_url, authentication, False)
        match = re.search(f"{job_name} #(\\d+)", _text)
        if match:
            job_number = match.group(1)
        if job_number != "":
            job_url = url2 + job_number \
                      + "/artifact/artifact.properties/*view*/"
            _text = _get_non_critical(job_url, authentication)
            if not _text:
                chart_versions.append(". . .")
            else:
                lines = _text.split('\n')
                for line in lines:
                    parts = line.split('=')
                    if len(parts) == 2:
                        name, value = parts
                        if name == 'CHART_VERSION':
                            chart_version = value
                            chart_versions.append(chart_version)
        else:
            chart_versions.append(". . .")

    return chart_versions


def get_baseline(chart_versions, corresponding_product_set, dict1, dict2):
    build_number_count = 0
    baseline = ""
    for i in chart_versions:
        if dict1[i] == "passed":
            if dict2[corresponding_product_set[build_number_count]] == "passed":
                baseline = i
                break
        build_number_count += 1
    return baseline, build_number_count


def get_history(url, authentication):
    authentication['Content-Type'] = 'application/json'
    _data = _get(url + "?expand=body.storage,version", authentication, True)

    existing_content = _data['body']['storage']['value']
    content_arr = existing_content.split("\n")
    return content_arr[1:]


def create_row(soup, table, color, link, text, style):
    tr = soup.new_tag("tr")
    table.append(tr)

    td = soup.new_tag("td")
    td["style"] = style + "  " + color
    tr.append(td)

    a = soup.new_tag("a", href=link, target="_blank")
    a["style"] = "color:white"
    a.string = text
    td.append(a)
    return tr


def create_column(soup, tr, color, link, text, style):
    td = soup.new_tag("td")
    td["style"] = style + "  " + color
    tr.append(td)

    a = soup.new_tag("a", href=link, target="_blank")
    a["style"] = "color:white"
    a.string = text
    td.append(a)


def get_color(result):
    if result == "passed":
        color = GREEN
    elif result == "failed":
        color = RED
    else:
        color = YELLOW
    return color


def generate_legend(styles, soup):
    legend_div = soup.new_tag("div", style="flex-basis: 0; padding-top: 30px;")

    h4 = soup.new_tag("h4")
    h4.string = "Legend:"
    legend_div.append(h4)

    table = soup.new_tag("table", style="border: 1px solid black;")

    tr1 = soup.new_tag("tr")
    td1 = soup.new_tag("td",
                       style=styles[3])
    td1.string = "Awaiting cENM"
    td2 = soup.new_tag("td", style=styles[0] + " " + BLACK)
    tr1.append(td1)
    tr1.append(td2)
    table.append(tr1)

    tr2 = soup.new_tag("tr")
    td3 = soup.new_tag("td", style=styles[3])
    td3.string = "Building"
    td4 = soup.new_tag("td", style=styles[0] + " " + YELLOW)
    td4.string = ". . ."
    tr2.append(td3)
    tr2.append(td4)
    table.append(tr2)

    tr3 = soup.new_tag("tr")
    td5 = soup.new_tag("td", style=styles[3])
    td5.string = "Pipeline Failed"
    td6 = soup.new_tag("td", style=styles[0] + " " + RED)
    td6.string = ". . ."
    tr3.append(td5)
    tr3.append(td6)
    table.append(tr3)

    tr4 = soup.new_tag("tr")
    td7 = soup.new_tag("td", style=styles[3])
    td7.string = "TAF Failed"
    td8 = soup.new_tag("td", style=styles[0] + " " + RED)
    td8.string = "1.4.0-30"
    tr4.append(td7)
    tr4.append(td8)
    table.append(tr4)

    tr5 = soup.new_tag("tr")
    td9 = soup.new_tag("td", style=styles[3])
    td9.string = "Build Successful"
    td10 = soup.new_tag("td", style=styles[0] + " " + GREEN)
    td10.string = "1.4.0-31"
    tr5.append(td9)
    tr5.append(td10)
    table.append(tr5)
    legend_div.append(table)

    return legend_div


def generate_introduction(soup):
    introduction_div = soup.new_tag("div")
    introduction_div["style"] = "flex-basis: 0;"

    p1 = soup.new_tag("p")
    p1.string = "This is the Cloud Native ENM SDKs Dashboard."
    introduction_div.append(p1)

    p2 = soup.new_tag("p")
    p2.string = "This dashboard is complementary to the " + \
                "Cloud Native ENM Maintrack Dashboard found here:"
    introduction_div.append(p2)

    p3 = soup.new_tag("p")
    a = soup.new_tag("a", href=DASHBOARD_URL)
    a.string = DASHBOARD_URL
    p3.append(a)
    introduction_div.append(p3)

    h5 = soup.new_tag("h5")
    h5.string = "Latest Install Baseline is the latest version of SDK" + \
                " for which SDK and corresponding cENM Product Set are GREEN"
    introduction_div.append(h5)

    return introduction_div


def generate_html(dict1, chart_versions, results,
                  pm_chart_versions, fm_chart_versions):

    style1 = "font-family: \"Ericsson Hilda\", Helvetica," + \
             " Arial, sans-serif; font-size: 1.4rem; padding:" + \
             " 10px; color: white; text-decoration: underline;" + \
             " text-align: center; background-color:"

    style2 = "font-family: \"Ericsson Hilda\", Helvetica, Arial," + \
             " sans-serif; padding: 10px; color: white; text-align:" + \
             " center; background-color:"

    style3 = "font-family: \"Ericsson Hilda\", Helvetica, Arial," + \
             " sans-serif; padding: 10px; color: white; text-align:" + \
             " center; background-color:"

    style4 = "font-family: \"Ericsson Hilda\", Helvetica, Arial," + \
             " sans-serif; font-size: 1.4rem; padding: 10px; color:" + \
             " black; text-align: center;"

    styles = [style1, style2, style3, style4]

    soup = BeautifulSoup("", "html.parser")
    main_div = soup.new_tag("div")
    soup.append(main_div)

    main_div.append(generate_introduction(soup))

    table_div = soup.new_tag("div")
    table_div["style"] = "flex-basis: 0; padding-top: 30px;"
    main_div.append(table_div)

    table = soup.new_tag("table")
    table_div.append(table)
    tr0 = soup.new_tag("tr")
    th1 = soup.new_tag("th", colspan='4',
                       style=styles[1] + " #89BA17")
    th1.string = "Cloud Native ENM SDK"
    tr0.append(th1)
    table.append(tr0)

    tr1 = soup.new_tag("tr")
    th2 = soup.new_tag("th", width='200',
                       style=styles[1] + " " + BLACK)
    th2.string = "cENM Product Set"
    th3 = soup.new_tag("th", width='200',
                       style=styles[1] + " " + BLACK)
    th3.string = "FM Chart"
    th4 = soup.new_tag("th", width='200',
                       style=styles[1] + " " + BLACK)
    th4.string = "PM Chart"
    th5 = soup.new_tag("th", width='200',
                       style=styles[1] + " " + BLACK)
    th5.string = "SDK"

    tr1.append(th2)
    tr1.append(th3)
    tr1.append(th4)
    tr1.append(th5)
    table.append(tr1)

    sync = 0
    dict1_list = list(dict1.items())
    for i in range(len(dict1)):
        value1 = dict1_list[i][1]
        color = get_color(value1)

        tr = create_row(soup, table, color, f"{PRODUCT_SET_URL}/"
                                            f"{drop}/{dict1_list[i][0]}/",
                        dict1_list[i][0], styles[0])
        table.append(tr)

        if dict1_list[i][0] in corresponding_product_set:
            value2 = results[i + sync]
            color = get_color(value2)

            create_column(soup, tr, color, f"{FM_TEMPLATES_NEXUS}"
                                           f"{fm_chart_versions[i + sync]}/",
                          fm_chart_versions[i + sync], styles[0])
            create_column(soup, tr, color, f"{PM_TEMPLATES_NEXUS}"
                                           f"{pm_chart_versions[i + sync]}/",
                          pm_chart_versions[i + sync], styles[0])
            create_column(soup, tr, color, f"{PUBLISH_URL}"
                                           f"{str(build_numbers[i + sync])}/",
                          chart_versions[i + sync], styles[0])

            curr_prod_set = corresponding_product_set[i + sync]
            while len(corresponding_product_set) > i + sync + 1 \
                    and corresponding_product_set[i
                                                  + sync
                                                  + 1] == curr_prod_set:
                sync += 1
                color = get_color(value1)

                tr = create_row(soup, table, color, f"{PRODUCT_SET_URL}/"
                                                    f"{drop}/{dict1_list[i][0]}/",
                                dict1_list[i][0], styles[0])
                table.append(tr)

                value2 = results[i + sync]
                color = get_color(value2)

                create_column(soup, tr, color,
                              f"{FM_TEMPLATES_NEXUS}"
                              f"{fm_chart_versions[i + sync]}/",
                              fm_chart_versions[i + sync],
                              styles[0])
                create_column(soup, tr, color,
                              f"{PM_TEMPLATES_NEXUS}"
                              f"{pm_chart_versions[i + sync]}/",
                              pm_chart_versions[i + sync],
                              styles[0])
                create_column(soup, tr, color,
                              f"{PUBLISH_URL}"
                              f"{str(build_numbers[i + sync])}",
                              chart_versions[i + sync],
                              styles[0])

        else:
            td = soup.new_tag("td")
            td["style"] = styles[0] + " " + BLACK
            tr.append(td)
            td = soup.new_tag("td")
            td["style"] = styles[0] + " " + BLACK
            tr.append(td)
            td = soup.new_tag("td")
            td["style"] = styles[0] + " " + BLACK
            tr.append(td)
            sync -= 1

    th = soup.new_tag("th")
    th["colspan"] = "4"
    th["style"] = styles[2] + " " + BLACK
    th.string = "LATEST INSTALL BASELINE: "
    a = soup.new_tag("a",
                     href=PUBLISH_URL + str(
                         build_numbers[build_number_count]),
                     style="color:white", target="_blank")
    a.string = baseline
    th.append(a)
    tr = soup.new_tag("tr")
    tr.append(th)
    table.append(tr)
    main_div.append(generate_legend(styles, soup))

    return soup.prettify()


def write_to_history(url, authentication, versions_string):
    authentication['Content-Type'] = 'application/json'
    _data = _get(url + "?expand=body.storage,version", authentication, True)

    version = _data['version']['number']
    version = version + 1

    existing_content = _data['body']['storage']['value']

    new_content = existing_content + "<p>" + versions_string + "</p>"

    data = {
        "id": "570356740",
        "type": "page",
        "title": "SDK History",
        "space": {
            "key": "TINH"
        },
        "version": {
            "number": version
        },
        "body": {
            "storage": {
                "value": new_content,
                "representation": "storage"
            }
        }
    }
    _post(HISTORY_URL, authentication, data)


def write_to_confluence(url, authentication, html):
    authentication['Content-Type'] = 'application/json'
    _data = _get(url, authentication, True)

    version = _data['version']['number']
    version = version + 1

    data = {
        "id": "550398751",
        "type": "page",
        "title": "Cloud Native ENM SDK Dashboard",
        "space": {
            "key": "TINH"
        },
        "version": {
            "number": version
        },
        "body": {
            "storage": {
                "value": f'<ac:structured-macro ac:name="html">'
                         f'<ac:plain-text-body><![CDATA[{html}]]>'
                         f'</ac:plain-text-body></ac:structured-macro>',
                "representation": "storage"
            }
        }
    }
    _post(CONFLUENCE_URL, authentication, data)


def prepare_history(chart_param, product_set_param):
    sdk_string = ""

    if chart_param != 'NA' and product_set_param != 'NA':
        sdk_string = "\n" + product_set_param + "," + chart_param

    if sdk_string != "":
        write_to_history(HISTORY_URL, AUTH, sdk_string)

    history = get_history(HISTORY_URL, AUTH)
    for i in range(len(history)):
        index = history[i].find("<")
        history[i] = history[i][:index]

    unique_numbers = []
    common_values = {}

    for entry in history:
        parts = entry.strip().split(',')
        if len(parts) == 2:
            if parts[0][:5] not in unique_numbers:
                unique_numbers.append(parts[0][:5])
                common_values[parts[0][:5]] = [[parts[0], parts[1]]]
            else:
                common_values[parts[0][:5]].append([parts[0], parts[1]])

    unique_numbers = sorted(unique_numbers,
                            key=lambda x: tuple(map(int, x.split("."))),
                            reverse=True)

    for key, reversed_arrays in common_values.items():
        common_values[key] = [arr[::-1] for arr in reversed(reversed_arrays)]

    return unique_numbers, common_values


def generate_tabs(unique_numbers, common_values):
    tab_string = ""
    tab_content_string = ""
    tab_count = 2
    style1 = "font-family: \"Ericsson Hilda\", Helvetica, Arial, " \
             "sans-serif; padding: 10px; color: white; text-align: center;"

    for tab in unique_numbers:
        tab_link = f"#tab{tab_count}"
        tab_item = f"<li style='{style1}'><a href='{tab_link}'>{tab}</a></li>"
        tab_string += tab_item

        table_head = (
            "<thead><tr>"
            "<th><div style='border: 1px solid black; width: 250px; "
            + style1
            + " background-color: " + BLACK + ";'>Product Set</div></th>"
            "<th><div style='border: 1px solid black; width: 250px; "
            + style1
            + " background-color: " + BLACK + ";'>FMSDK Chart</div></th>"
            "</tr></thead>"
        )
        table_body = "<tr><td colspan='2' style='border-top: 1px" +\
                     " solid black;'></td></tr>"
        for line in common_values[tab]:
            product_href = CENM_TEMPLATE.format(line[0][:5], line[0])
            chart_href = SDK_TEMPLATES.format(line[1])
            row = (
                "<tr>"
                "<td style='border: 1px solid black; "
                + style1
                + " padding: 10px; text-align: center;'>"
                "<a href='"
                + product_href
                + "'>"
                + line[0]
                + "</a></td>"
                "<td style='border: 1px solid black; "
                + style1
                + " padding: 10px; text-align: center;'>"
                "<a href='"
                + chart_href
                + "'>"
                + line[1]
                + "</a></td>"
                "</tr>"
            )
            table_body += row

        table = (
            "<table style='border: 1px solid black; "
            "border-collapse: separate; width: 500px;'>"
            + table_head
            + "<tbody>"
            + table_body
            + "</tbody></table>"
        )
        tab_content = (
            "<div id='tab" + str(tab_count)
            + "' class='tab-content'>" + table + "</div>"
        )
        tab_content_string += tab_content
        tab_count += 1

    return tab_string, tab_content_string


drop = get_drop(DROP_URL, AUTH)
statuses, versions = get_cenm_dashboard(CENM_URL, AUTH)
build_numbers, results,\
        corresponding_product_set, \
        current_product_set = get_builds(PUBLISH_URL, AUTH)
chart_versions = get_versions(results, PUBLISH_URL, BUILDMANAGER_URL,
                              AUTH, 'sdk-csar-buildmanager')
fm_chart_versions = get_versions(results, PUBLISH_URL, FM_TEMPLATES_URL,
                                 AUTH, 'fm-sdk-templates')
pm_chart_versions = get_versions(results, PUBLISH_URL, PM_TEMPLATES_URL,
                                 AUTH, 'pm-sdk-templates')
cenm_dict = merge_arrays(versions, statuses)
fmsdk_dict = merge_arrays(chart_versions, results)
fm_dict = merge_arrays(fm_chart_versions, results)
pm_dict = merge_arrays(pm_chart_versions, results)
baseline, build_number_count = get_baseline(chart_versions,
                                            corresponding_product_set,
                                            fmsdk_dict, cenm_dict)
html = generate_html(cenm_dict, chart_versions, results,
                     pm_chart_versions, fm_chart_versions)
unique_numbers, common_values = prepare_history(chart_param, product_set_param)
tab_string, tab_content_string = generate_tabs(unique_numbers, common_values)
tab_content_string = BeautifulSoup(tab_content_string, 'html.parser')
tab_content_string = tab_content_string.prettify()
final_html = template.format(dashboard_html=html,
                             tabs=tab_string, tabs_content=tab_content_string)
write_to_confluence(CONFLUENCE_URL, AUTH, final_html)

