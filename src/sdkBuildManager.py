#!/usr/bin/env python
import datetime
import fileinput
import glob
import json
import math
import os
import subprocess
import sys
import time

try:
    import yaml as pyyaml
except ImportError:
    raise SystemExit('Module "pyyaml" not installed in python environment!'
                     '\nRun: pip install PyYAML')

import argparse
import re
import shutil
import tarfile
from collections import OrderedDict
from os import listdir, rename
from os.path import isdir, dirname, join, basename, exists, splitext, \
    abspath, expandvars, expanduser
from typing import List, Any, Tuple, Optional, Dict
import uuid

VERBOSE = False


class Base:
    @staticmethod
    def _log(level, tag, message) -> None:
        print('{0}: {1}: {2}'.format(level, tag, message))

    def info(self, tag: str, message: str) -> None:
        self._log('INFO', tag, message)

    def warn(self, tag: str, message: str) -> None:
        self._log('WARN', tag, message)

    def debug(self, tag: str, message: str) -> None:
        if VERBOSE:
            self._log('DEBUG', tag, message)

    @staticmethod
    def which(binary_file):
        try:
            Base()._execute(['which', binary_file])
            return True
        except SystemError:
            return False

    def _execute(self, command: List[str], cwd=None, log=True) -> int:
        _start = time.perf_counter()
        process = subprocess.Popen(
            command, cwd=cwd,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for line in iter(process.stdout.readline, b''):
            if log:
                self.info('PROCESS', line.decode().strip())
        process.stdout.close()
        process.wait()
        _end = time.perf_counter()
        if process.returncode != 0:
            raise SystemError(process.returncode)
        return math.ceil(_end - _start)

    @staticmethod
    def replace_value(file_path: str, chart_name: str, string_to_replace: str):
        if exists(file_path):
            with fileinput.FileInput(file_path, inplace=True) as _contents:
                for line in _contents:
                    print(line.replace(string_to_replace, chart_name), end='')

    @staticmethod
    def get_command_flags(command, *options) -> Optional[str]:
        sdk_cfg = expandvars(expanduser('~/.cenm_sdk/config.yaml'))
        if exists(sdk_cfg):
            _yaml = Yaml()
            _cfg = _yaml.load(sdk_cfg)
            return _yaml.get_flags(_cfg, command, *options)
        return None


class Tar(Base):

    def extract_tar(self, tar_file: str, overwrite: bool) -> str:
        templates_dir = dirname(tar_file)
        _tgz = tarfile.open(tar_file)
        _root = _tgz.getnames()[0]

        destination = join(templates_dir, _root)
        if isdir(destination) and not overwrite:
            raise Exception('Can\'t extract {0} as directory {1} '
                            'already exists'.format(tar_file, destination))

        self.info('TAR', 'Extracting {0} to {1}'.format(
            tar_file, templates_dir))
        _tgz.extractall(templates_dir)
        return destination


class Sed:
    @staticmethod
    def replace_docker_arg(arg: str, value: str, data: str) -> str:
        return re.sub(r'(ARG {0}=).*'.format(arg),
                      r'\g<1>{0}'.format(value), data)


class Yaml(Base):

    def __init__(self) -> None:
        super().__init__()

    def load(self, file_path: str) -> OrderedDict:
        class OrderedLoader(pyyaml.SafeLoader):
            pass

        def construct_mapping(loader, node):
            loader.flatten_mapping(node)
            return OrderedDict(loader.construct_pairs(node))

        OrderedLoader.add_constructor(
            pyyaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            construct_mapping)
        self.debug('YAML', 'Loading {0}'.format(file_path))
        with open(file_path, 'r') as stream:
            return pyyaml.load(stream, OrderedLoader)

    def dump(self, data: OrderedDict, file_path: str, **kwds) -> None:
        class OrderedDumper(pyyaml.SafeDumper):
            pass

        def _dict_representer(dumper, yaml_data):
            return dumper.represent_mapping(
                pyyaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                yaml_data.items())

        def _none_representer(dumper, _):
            return dumper.represent_scalar(
                'tag:yaml.org,2002:null',
                '')

        OrderedDumper.add_representer(OrderedDict, _dict_representer)
        OrderedDumper.add_representer(type(None), _none_representer)

        self.debug('YAML', 'Writing {0}'.format(file_path))
        with open(file_path, 'w') as stream:
            pyyaml.dump(data, stream, OrderedDumper,
                        default_flow_style=False, **kwds)

    def get_build_options(self, sdk_input_path: str,
                          chart_name: str) -> OrderedDict:
        _opts_path = join(sdk_input_path, chart_name, 'config', 'build.yaml')
        self.debug('YAML', 'Loading build options from {0}'.format(_opts_path))
        return self.load(_opts_path)

    def merge(self, base: Any, changes: Any) -> None:
        if isinstance(changes, list):
            base.extend(changes)
        else:
            for c_key, c_value in changes.items():
                if c_key not in base:
                    base[c_key] = c_value
                elif isinstance(c_value, OrderedDict):
                    self.merge(base[c_key], c_value)
                else:
                    base[c_key] = c_value

    def __traverse(self, map_data: Dict, keys: Tuple[Any]) -> Optional[Dict]:
        _flags = map_data.get(keys[0])
        if len(keys) > 1:
            return self.__traverse(_flags, keys[1:])
        return _flags

    def get_flags(self, config: Dict, command: str, *args) -> Optional[str]:
        _flags = config.get(command)
        if _flags:
            _flags = self.__traverse(_flags, args)
            if _flags:
                _t = []
                for _flag_name in _flags:
                    if _flags[_flag_name] is not None:
                        _t.append('{0}={1}'.format(
                            _flag_name, _flags[_flag_name]))
                    else:
                        _t.append(_flag_name)
                return ' '.join(_t)
        return None


class Chart(Base):

    def __init__(self) -> None:
        self._yaml = Yaml()

    def generate_custom_chart(self,
                              templates_dir: str, chart_name: str,
                              sdk_input_path: str, output_dir: str,
                              overwrite: bool,
                              repository: str) -> Tuple[str, str]:
        if output_dir:
            custom_dir = join(output_dir, chart_name)
        else:
            custom_dir = join(dirname(templates_dir), chart_name)

        self.info('CHART', 'Generating custom chart for {0} from {1}'.format(
            chart_name, templates_dir))

        if isdir(custom_dir):
            if not overwrite:
                raise NameError('A custom chart named "{0}" already '
                                'exists in {1}'.format(chart_name, custom_dir))
            else:
                self.debug('CHART', 'Removing existing {0}'.format(custom_dir))
                shutil.rmtree(custom_dir)

        build_opts = self._yaml.get_build_options(sdk_input_path, chart_name)
        image_opts = build_opts[chart_name]
        sdk_type = basename(sdk_input_path).lower()[0:2]

        shutil.copytree(templates_dir, custom_dir)

        _chart = join(custom_dir, 'chart')
        inter_name = listdir(_chart)[0]

        self.info('CHART', 'Updating {0} with new name "{1}"'.format(
            custom_dir, chart_name))
        inter_dir = join(_chart, inter_name)
        new_inter_dir = join(dirname(inter_dir), chart_name)
        rename(inter_dir, new_inter_dir)

        chart_yaml = join(new_inter_dir, 'Chart.yaml')
        values_yaml = join(new_inter_dir, 'values.yaml')

        chart_data = self._yaml.load(chart_yaml)

        desc = image_opts.get('chart-description') if image_opts.get(
            'chart-description') else 'Helm chart for {0}'.format(chart_name)
        chart_version = image_opts.get('chart-version')
        if not chart_version:
            raise LookupError('No chart-version for {0} found in '
                              'options'.format(chart_name))

        self.info('CHART', 'Chart name: {0}'.format(chart_name))
        chart_data['name'] = chart_name
        self.info('CHART', 'Chart version: {0}'.format(chart_version))
        chart_data['version'] = chart_version
        self.info('CHART', 'Chart description: {0}'.format(desc))
        chart_data['description'] = desc

        self._yaml.dump(chart_data, chart_yaml)

        values_data = self._yaml.load(values_yaml)

        del values_data['images'][inter_name]
        values_data['images'][chart_name] = {
            'name': chart_name,
            'tag': image_opts.get('image-version')
        }
        imagename = f'{sdk_type}-sdk-models'
        imgname_toremove = f'{sdk_type}-sdk-remove-models'
        name = f'models-install-{sdk_type}'
        uninstall_name = f'remove-models-{sdk_type}'

        values_data['images'][imagename] = {
            'name': "-".join([chart_name, name]),
            'tag': image_opts.get('image-version')
        }

        values_data['images'][imgname_toremove] = {
            'name': "-".join([chart_name, uninstall_name]),
            'tag': image_opts.get('image-version')
        }
        replicas_key = 'replicas-{0}'.format(inter_name)
        replicas = values_data.pop(replicas_key)
        values_data['replicas-{0}'.format(chart_name)] = replicas

        service_name = image_opts.get('servicename', chart_name)

        values_data['service']['name'] = service_name
        values_data['service']['sgname'] = service_name
        self.info('CHART', 'Setting service.name to {0}'.format(service_name))
        global_reg_url = repository.split('/')[0]
        repo_path = '/'.join(repository.split('/')[1:])

        values_data['global']['registry'] = {
            'url': global_reg_url
        }
        values_data['imageCredentials']['repoPath'] = repo_path

        k_monitoring = 'eric-enm-monitoring'
        mon_image = values_data['images'][k_monitoring]['name']
        if mon_image in build_opts:
            _tag = build_opts[mon_image]['image-version']
            values_data['images'][k_monitoring]['tag'] = _tag
            self.info('CHART', 'Updating {0} to {1}'.format(mon_image, _tag))
        else:
            _tag = values_data['images'][k_monitoring]['tag']
            self.info('CHART', 'No {0} build options set, '
                               'leaving as {1}'.format(k_monitoring, _tag))

        self._yaml.dump(values_data, values_yaml)
        foldername = f'{chart_name}-models-{sdk_type}'
        torename='/'.join([custom_dir,foldername])
        existingfolder = f'eric-enm-custom-models-{sdk_type}-oneflow'
        rename('/'.join([custom_dir,existingfolder]), torename)

        ingress_yaml = join(new_inter_dir, 'templates', 'eric_ingress.yaml')
        ingress_yaml_ipv6 = join(new_inter_dir, 'templates',
                                 'eric_ingress_ipv6.yaml')
        svc_ipv6 = join(new_inter_dir, 'templates', 'svc_ipv6.yaml')

        tplates = [ingress_yaml, ingress_yaml_ipv6, svc_ipv6]
        _t_types = ['eric-enmsg-custom-fm-oneflow',
                    'eric-enmsg-custom-pm-oneflow']

        for template in tplates:
            for _type in _t_types:
                Base().replace_value(template, service_name,
                                     _type)

        return custom_dir, chart_version

    def _merge_values_yaml(self, chart_path: str, chart_name: str,
                           sdk_input_path: str):
        values_yaml = join(chart_path, 'chart', chart_name, 'values.yaml')
        values_inputs = join(sdk_input_path, chart_name, 'config',
                             'values.yaml')

        self.info('CHART', 'Merging {0} into {1}'.format(
            values_inputs, values_yaml))
        data = self._yaml.load(values_yaml)
        merge = self._yaml.load(values_inputs)

        self._yaml.merge(data, merge)
        self._yaml.dump(data, values_yaml)

    def _merge_global_properties(self, chart_path: str, chart_name: str,
                                 sdk_input_path: str) -> None:

        gp = join(sdk_input_path, chart_name, 'config',
                  'global-properties.json')

        # rename template globalproperties.yaml
        appconfig = join(chart_path, 'chart', chart_name, 'appconfig')
        gp_template = join(appconfig, 'configmaps', 'globalproperties.yaml')
        new_name = 'gp-' + chart_name + '.yaml'

        template_gp_path = join(dirname(gp_template), new_name)
        rename(gp_template, template_gp_path)

        if exists(gp):
            with open(gp, 'r') as _r:
                gp_data = json.load(_r)

            gp_data_str = []
            for _key, _value in gp_data.items():
                gp_data_str.append('{0}={1}\n'.format(_key, _value))

            template_gp = self._yaml.load(template_gp_path)
            if 'global.properties' in template_gp:
                for kv_pair in template_gp['global.properties'].split('\n'):
                    gp_data_str.append('{0}\n'.format(kv_pair))

            gp_data_str = '  '.join(gp_data_str)

            with open(template_gp_path, 'w') as _w:
                _w.write('global.properties: |\n  ')
                _w.write(''.join(gp_data_str))

        p_volumes = join(appconfig, 'volumes.yaml')
        volumes = self._yaml.load(p_volumes)
        for volume in volumes:
            if volume['name'] == 'gp':
                volume['configMap']['name'] = splitext(new_name)[0]
                break
        self._yaml.dump(volumes, p_volumes)

    def _merge_named_yaml(self, chart_path: str, chart_name: str,
                          sdk_input_path: str) -> None:
        """
        Merge any yaml files in {sdk_input_path}/sdk/<type>sdk/{chart_name}/config
         into the custom chart. The files in the config dir must be the same
         format as the files in the custom chart.
        :param chart_path: PAth to the chart
        :param chart_name: The chart name
        :param sdk_input_path: Path to chart inputs

        """
        config = join(sdk_input_path, chart_name, 'config')

        yaml_files = glob.glob1(config, "*.yaml")
        yaml_files.remove('build.yaml')

        # values.yaml has its own handling
        yaml_files.remove('values.yaml')
        yaml = Yaml()

        appconfig = join(chart_path, 'chart', chart_name, 'appconfig')
        for yaml_file in yaml_files:
            m_yaml = join(config, yaml_file)
            c_yaml = join(appconfig, yaml_file)

            if exists(c_yaml):
                self.info('CHART', 'Merging {0} with {1}'.format(
                    m_yaml, c_yaml))
                c_data = yaml.load(c_yaml)
                m_data = yaml.load(m_yaml)

                yaml.merge(c_data, m_data)
                yaml.dump(c_data, c_yaml)
            else:
                self.info('CHART', 'Copying {0} to {1}'.format(m_yaml, c_yaml))
                shutil.copy(m_yaml, c_yaml)

    def merge_custom_chart_config(self, chart_path: str, chart_name: str,
                                  sdk_input_path: str) -> None:
        self._merge_values_yaml(chart_path, chart_name, sdk_input_path)
        self._merge_global_properties(chart_path, chart_name, sdk_input_path)
        self._merge_named_yaml(chart_path, chart_name, sdk_input_path)

    def package(self, chart_path: str, chart_name: Optional[str] = None,
                sdk_input_path: Optional[str] = None) -> str:

        chart_version = None
        if chart_name:
            a_chart = join(chart_path, 'chart', chart_name)
        else:
            a_chart = chart_path
            _yaml = Yaml().load(join(chart_path, 'Chart.yaml'))
            chart_name = _yaml['name']
            chart_version = _yaml['version']

        if sdk_input_path:
            build_opts = self._yaml.get_build_options(
                sdk_input_path, chart_name)
            chart_opts = build_opts[chart_name]
            chart_version = chart_opts.get('chart-version')

        o_path = dirname(chart_path)

        h_dep_up = ['helm', '--debug', 'dependency', 'update', a_chart]
        _flags = self.get_command_flags('helm', 'dependency', 'update')
        if _flags:
            h_dep_up.insert(4, _flags)

        h_lint = ['helm', '--debug', 'lint', a_chart]
        _flags = self.get_command_flags('helm', 'lint')
        if _flags:
            h_lint.insert(3, _flags)

        h_pkg = ['helm', '--debug', 'package', a_chart, '-d', o_path]
        _flags = self.get_command_flags('helm', 'package')
        if _flags:
            h_pkg.insert(4, _flags)

        cmds = (
            ('Updating {0} chart dependencies'.format(chart_name),
             h_dep_up),
            ('Linting {0} chart'.format(chart_name),
             h_lint),
            ('Packaging chart {0} to {1}'.format(chart_name, o_path),
             h_pkg)
        )

        for helm_cmd in cmds:
            info = helm_cmd[0]
            cmd = helm_cmd[1]
            self.info('CHART', info)
            _time = self._execute(cmd)
            self.info('CHART', 'Helm took {0} seconds'.format(_time))

        chart_file = join(o_path, '{0}-{1}.tgz'.format(
            chart_name, chart_version))
        if not exists(chart_file):
            raise FileNotFoundError('File {0} not found!'.format(chart_file))
        self.info('CHART', 'Generated {0}'.format(chart_file))
        return chart_file


class Docker(Base):
    def __init__(self) -> None:
        self._yaml = Yaml()

    def _update_dockerfile_packages_models(
        self,
        chart_name: str,
        chart_dir: str,
        sdk_input_path: str,
        custommodelfolder: str,
        image_content_folder: str,
        models_folder: str,
    ):
        image_content = join(chart_dir, custommodelfolder, image_content_folder)
        inputs_jboss = join(sdk_input_path, chart_name, models_folder)

        if not exists(inputs_jboss):
            raise FileNotFoundError('Folder {0} not found Create and place rpms !'.format(inputs_jboss))

        files = glob.glob1(inputs_jboss, "*.rpm")
        if not files:
           raise SystemExit('rpm files are not found !!! in models/uninstall folder')
        for pkg in listdir(inputs_jboss):
            pkg = str(pkg)
            abs_pkg = join(inputs_jboss, pkg)
            target = join(image_content, pkg)
            self.info('DOCKER', 'Copying {0} to {1}'.format(abs_pkg, target))
            shutil.copyfile(abs_pkg, target)


    def _update_dockerfile_packages(self, chart_name: str,
                                    chart_dir: str,
                                    sdk_input_path: str):

        image_content = join(chart_dir, 'image_content')
        inputs_jboss = join(sdk_input_path, chart_name, 'jboss')

        for pkg in listdir(inputs_jboss):
            pkg = str(pkg)
            abs_pkg = join(inputs_jboss, pkg)
            target = join(image_content, pkg)

            self.info('DOCKER', 'Copying {0} to {1}'.format(abs_pkg, target))
            shutil.copyfile(abs_pkg, target)

    def _update_dockerfile_scripts(self, chart_name: str, chart_dir: str,
                                   sdk_input_path: str):
        i_scripts = join(sdk_input_path, chart_name, 'scripts')
        e_scripts = join(i_scripts, 'scriptEntries.txt')

        scripts_entries = []
        if exists(e_scripts):
            with open(e_scripts, 'r') as _r:
                scripts_entries = _r.readlines()

        if not scripts_entries:
            return

        image_content = join(chart_dir, 'image_content')

        dockerfile = join(chart_dir, 'Dockerfile')
        with open(dockerfile) as _reader:
            s_dockerfile = _reader.readlines()

        for entry in scripts_entries:
            name, location = entry.split(':')
            location = location.strip()
            name = name.strip()
            script = join(i_scripts, name)

            if not exists(script):
                raise FileNotFoundError(script)

            shutil.copy2(script, image_content)
            self.info('DOCKER',
                      'Adding {0} to image under {1}'.format(name, location))
            s_dockerfile.append(
                'COPY --chown=jboss_user:root image_content/{0} {1}'.format(
                    name, location))

        s_dockerfile = "".join(s_dockerfile)

        with open(dockerfile, 'w') as _writer:
            _writer.write(s_dockerfile)

    def generate_images(self, chart_dir: str, sdk_input_path: str,
                        repository: str) -> None:

        dockerfile = join(chart_dir, 'Dockerfile')
        chart_name = basename(chart_dir)

        self._update_dockerfile_packages(chart_name, chart_dir, sdk_input_path)
        self._update_dockerfile_scripts(chart_name, chart_dir, sdk_input_path)

        with open(dockerfile) as _reader:
            s_dockerfile = "".join(_reader.readlines())

        build_opts = self._yaml.get_build_options(sdk_input_path, chart_name)

        sdk_type = basename(sdk_input_path).lower()
        build_opt_keys = 'eric-enm-{0}'.format(sdk_type)

        sdk_image_version = build_opts[build_opt_keys]['image-version']

        if 'image-repository' in build_opts[build_opt_keys]:
            sdk_image_repository = build_opts[
                build_opt_keys]['image-repository']
        else:
            sdk_image_repository = repository

        self.info('DOCKER', 'Setting main FROM image repository to {0}'.format(
            sdk_image_repository))

        key_base = 'ERIC_ENM_{0}'.format(sdk_type.upper())
        key_repo = '{0}_IMAGE_REPO'.format(key_base)
        key_tag = '{0}_IMAGE_TAG'.format(key_base)

        s_dockerfile = Sed.replace_docker_arg(
            key_repo, sdk_image_repository, s_dockerfile)

        self.info('DOCKER', 'Setting main FROM image tag to {0}'.format(
            sdk_image_version))
        s_dockerfile = Sed.replace_docker_arg(
            key_tag, sdk_image_version, s_dockerfile)

        with open(dockerfile, 'w') as _writer:
            _writer.write(s_dockerfile)

    def generate_images_model(self, chart_dir: str, sdk_input_path: str,
                        repository: str, isinstall: bool) -> None:

        sdk_type = basename(sdk_input_path).lower()[0:2]
        chart_name = basename(chart_dir)
        foldername = f'{chart_name}-models-{sdk_type}'

        if isinstall:
            dockerfile = join(chart_dir, foldername, "Dockerfile")
            self._update_dockerfile_packages_models(
                chart_name,
                chart_dir,
                sdk_input_path,
                foldername,
                "image_content",
                "models",
            )
        else:
            dockerfile = join(chart_dir, foldername, "Dockerfile-RemoveModels")
            self._update_dockerfile_packages_models(
                chart_name,
                chart_dir,
                sdk_input_path,
                foldername,
                "image_content_removemodels",
                "uninstall",
            )

        with open(dockerfile) as _reader:
            s_dockerfile = "".join(_reader.readlines())

        model_core_image_version = 'latest'
        model_image_repository = repository

        self.info('DOCKER', 'Setting main FROM image repository to {0}'.format(
            model_image_repository))

        key_base = 'ERIC_ENM_MODELS_CORE'
        key_repo = f'{key_base}_IMAGE_REPO'
        key_tag = f'{key_base}_IMAGE_TAG'

        s_dockerfile = Sed.replace_docker_arg(
            key_repo, model_image_repository, s_dockerfile)

        self.info('DOCKER', 'Setting main FROM image tag to {0}'.format(
            model_core_image_version))
        s_dockerfile = Sed.replace_docker_arg(
            key_tag, model_core_image_version, s_dockerfile)

        with open(dockerfile, 'w') as _writer:
            _writer.write(s_dockerfile)

    def _build_main_image(self, chart_dir: str, repository: str,
                          sdk_input_path: str):
        dockerfile = join(chart_dir, 'Dockerfile')

        image_name = basename(chart_dir)

        build_opts = self._yaml.get_build_options(sdk_input_path, image_name)
        version = build_opts[image_name]['image-version']

        tag = '{0}/{1}:{2}'.format(repository, image_name, version)

        command = [
            'docker', 'build', '--network=host',
            '--file', dockerfile, '-t', tag, chart_dir
        ]

        self.info('DOCKER', 'Building {0} with tag {1}'.format(
            dockerfile, tag))
        _time = self._execute(command, chart_dir)
        self.info('DOCKER', 'Build took {0} seconds'.format(_time))

        return tag

    def _build_models_image(
        self,
        chart_dir: str,
        repository: str,
        sdk_input_path: str,
        docker_file: str,
        isinstall: bool,
    ) -> str:
        self.info("DOCKER", "Building model image")
        sdk_type = basename(sdk_input_path).lower()[0:2]
        chart_name = basename(chart_dir)
        folder_name = f"{chart_name}-models-{sdk_type}"
        dockerfile = join(chart_dir, folder_name, docker_file)
        build_opts = self._yaml.get_build_options(sdk_input_path, basename(chart_dir))
        tmpdir = join(chart_dir,folder_name)

        if isinstall:
            name = f'-models-install-{sdk_type}'
            image_name = chart_name+name
            version = build_opts[chart_name]["image-version"]
            tag = "{0}/{1}:{2}".format(repository, image_name, version)
        else:
            name = f'-remove-models-{sdk_type}'
            image_name = chart_name+name
            tmpdir = join(chart_dir, folder_name)
            version = build_opts[chart_name]["image-version"]
            tag = "{0}/{1}:{2}".format(repository, image_name, version)

        command = [
            "docker",
            "build",
            "--network=host",
            "--file",
            dockerfile,
            "-t",
            tag,
            tmpdir,
        ]
        self.info("DOCKER", "Building {0} with tag {1}".format(dockerfile, tag))
        _time = self._execute(command, chart_dir)
        self.info("DOCKER", "Build took {0} seconds".format(_time))
        return tag

    def build_image(self, chart_dir: str, repository: str,
                    sdk_input_path: str) -> List[str]:
        tag_main = self._build_main_image(chart_dir, repository,
                                          sdk_input_path)
        tag_model = self._build_models_image(
            chart_dir, repository, sdk_input_path, "Dockerfile", True
        )
        tag_model_uninstall = self._build_models_image(
            chart_dir, repository, sdk_input_path, "Dockerfile-RemoveModels", False
        )

        return [x for x in [tag_main, tag_model, tag_model_uninstall] if x]

    def _exec_with_retry(self, command: List[str]) -> int:
        try_count = 0
        while True:
            try:
                return self._execute(command, log=VERBOSE)
            except SystemError as error:
                try_count += 1
                if try_count >= 3:
                    raise error
                self.warn('DOCKER', 'Docker command failed, trying again ...')

    def push_images(self, tags: List[str]) -> None:
        for tag in tags:
            command = ['docker', 'push', tag]
            self.info('DOCKER', 'Pushing {0}'.format(tag))
            _time = self._exec_with_retry(command)
            self.info('DOCKER', 'Push took {0} seconds'.format(_time))

    def load_images(self, docker_tar: str) -> None:
        command = ['docker', 'load', '--input', docker_tar]
        _time = self._exec_with_retry(command)
        self.info('DOCKER', 'Load took {0} seconds'.format(_time))

    def exists(self, tag: str):
        command = ['docker', 'image', 'inspect', tag]
        try:
            self._execute(command, log=False)
            return True
        except SystemError:
            return False

    def remove(self, tags: List[str]) -> None:
        for tag in tags:
            command = ['docker', 'rmi', '--force', tag]
            self.info('DOCKER', 'Removing tag {0}'.format(tag))
            self._execute(command, log=VERBOSE)

    def retag(self, tag, new_tag):
        self.info('DOCKER', 'Re-tagging {0} to {1}'.format(tag, new_tag))
        command = ['docker', 'tag', tag, new_tag]
        self._execute(command, log=VERBOSE)

    def preparecsar(self, output_dir: str, csar_name: str,
                    sdk_inputpath: str, am_package_manager: str,
                    light: bool):
        output_dir = abspath(output_dir)
        self.info('DOCKER', 'Re-Building Csar with Custom dir volume')
        for custom_chart_name in listdir(output_dir):
            if custom_chart_name.endswith(".tgz"):
                volume = output_dir + ':' + output_dir
                docker_sock = '/var/run/docker.sock:/var/run/docker.sock'

                manifest_path = abspath(
                    join(basename(__file__), '..', '..', 'templates', 'csar',
                         'manifest'))
                _parent = join(output_dir, 'manifest')
                if not isdir(_parent):
                    os.makedirs(_parent, exist_ok=True)

                for _file in os.listdir(manifest_path):
                    shutil.copy(join(manifest_path, _file), _parent)

                vnfd_path = abspath(
                    join(basename(__file__), '..', '..', 'templates', 'csar',
                         'vnfd'))
                _parent = join(output_dir, 'vnfd')
                if not isdir(_parent):
                    os.makedirs(_parent, exist_ok=True)

                for _file in os.listdir(vnfd_path):
                    shutil.copy(join(vnfd_path, _file), _parent)

                # make dir under output_dir
                # mkdir(output_dir+'/scripts')
                chartname = splitext(custom_chart_name)[0]
                chart_name_folder = re.split(r'(\-\d.+|\-\d+(\.\d+))$',
                                             chartname)
                rpmlocation = abspath(
                    sdk_inputpath + '/' + chart_name_folder[0] + '/models/')

                _parent = join(output_dir, 'scripts')
                if not isdir(_parent):
                    os.makedirs(_parent, exist_ok=True)

                for _file in os.listdir(rpmlocation):
                    shutil.copy(join(rpmlocation, _file), _parent)

                Base().replace_value(
                    output_dir + '/manifest/fmsdk_descriptor.mf',
                    chart_name_folder[0], '<<PRODUCT>>')
                Base().replace_value(
                    output_dir + '/vnfd/fmsdk_descriptor.yaml',
                    chart_name_folder[0], '<<PRODUCT>>')
                Base().replace_value(
                    output_dir + '/vnfd/fmsdk_descriptor.yaml',
                    str(uuid.uuid1()), '<<DESCRIPTOR_ID>>')
                Base().replace_value(
                    output_dir + '/vnfd/fmsdk_descriptor.yaml',
                    str(custom_chart_name), '<<CHART>>')
                command = ['docker', 'run', '--rm', '-v', volume,
                           '-v', docker_sock, '-w', output_dir,
                           am_package_manager,
                           'generate', '--helm3', '-hm', custom_chart_name,
                           '--name', csar_name,
                           '-sc', 'scripts',
                           '-mf', 'manifest/fmsdk_descriptor.mf',
                           '-vn', 'vnfd/fmsdk_descriptor.yaml',
                           '--set', 'images.eric-enm-monitoring.enabled=false']
                if light:
                    command.append('--no-images')
                self.info('DOCKER',
                          'Creating CSAR from {0} '.format(custom_chart_name))
                self._execute(command)
            else:
                self.info('DOCKER', 'no chart found')


class SdkBuildManager(Base):

    def __init__(self) -> None:
        super().__init__()
        self._chart = Chart()
        self._docker = Docker()

    def generate_chart(self, sdk_path: str, sdk_input_path: str,
                       repository: str, output_dir: str,
                       overwrite: bool) -> None:
        """
        Take the SDK chart template and create a custom SDK chart
        with Dockerfile. The Dockerfile wil lbe build and pushed to
        the specified repository
        :param sdk_path: Path to SDK templates
        :param sdk_input_path: Path to artifacts to include in chart/image
        :param repository: Local docker repository
        :param output_dir: Where to generate the custom chart
        :param overwrite: Overwrite existing files if they exist.
        :return:
        """
        sdk_path = abspath(sdk_path)
        sdk_input_path = abspath(sdk_input_path)
        output_dir = abspath(output_dir)

        tar = Tar()
        if not isdir(sdk_path) and tarfile.is_tarfile(sdk_path):
            templates_dir = tar.extract_tar(sdk_path, overwrite)
        else:
            templates_dir = sdk_path

        for custom_chart_name in listdir(sdk_input_path):
            chart_dir, chart_version = self._chart.generate_custom_chart(
                templates_dir, custom_chart_name,
                sdk_input_path, output_dir,
                overwrite, repository)

            self._chart.merge_custom_chart_config(
                chart_dir, custom_chart_name, sdk_input_path)

            self._docker.generate_images(chart_dir, sdk_input_path,
                                         repository)

            self._docker.generate_images_model(
                chart_dir, sdk_input_path, repository, True
            )

            self._docker.generate_images_model(
                chart_dir, sdk_input_path, repository, False
            )

            tags = self._docker.build_image(chart_dir, repository,
                                            sdk_input_path)
            self._docker.push_images(tags)

            self._chart.package(chart_dir, custom_chart_name, sdk_input_path)

    def integration_chart(self, chart_yaml: str, template: str,
                          output_dir: str) -> Tuple[str, str, str]:
        _chart = Yaml().load(chart_yaml)
        _name = _chart['name']
        _version = _chart['version']

        _name_version = '{0}-{1}'.format(_name, _version)

        sdk_integ_chart = join(output_dir, 'integration', _name_version)

        tar = Tar()
        e_template = tar.extract_tar(template, True)

        if isdir(sdk_integ_chart):
            shutil.rmtree(sdk_integ_chart)
        shutil.copytree(e_template, sdk_integ_chart)

        integ_chart = Yaml()
        chart_data = integ_chart.load(join(sdk_integ_chart, 'Chart.yaml'))

        integ_chart.merge(chart_data, _chart)

        integ_chart.dump(chart_data, join(sdk_integ_chart, 'Chart.yaml'))

        helm = Chart()
        return helm.package(sdk_integ_chart), _name, _version

    def prepare_csar(self, csar_name: str, csar_version: str,
                     chart: str, product_set: str,
                     output_dir: str) -> Tuple[str, str, str]:

        build_dir = join(
            output_dir, 'csar',
            '{0}-{1}'.format(csar_name, csar_version))
        if not isdir(build_dir):
            os.makedirs(build_dir)

        _csar_charts = join(build_dir, 'charts')
        _chart_filename = basename(chart)
        if not isdir(_csar_charts):
            os.makedirs(_csar_charts, exist_ok=True)
        shutil.copyfile(chart, join(_csar_charts, _chart_filename))

        templates = abspath(join(dirname(__file__), '..', 'templates', 'csar'))
        if not isdir(templates):
            _git = abspath(join(dirname(__file__),
                                '..', 'fmsdk_bm_csar_source'))
            if isdir(_git):
                templates = _git
            else:
                raise FileNotFoundError(templates)

        t_manifest = join(templates, 'manifest', 'fmsdk_descriptor.mf')
        manifest = join(build_dir, 'manifest', 'sdk_descriptor.mf')
        os.makedirs(dirname(manifest), exist_ok=True)
        shutil.copy(t_manifest, manifest)

        t_vnfd = join(templates, 'vnfd', 'fmsdk_descriptor.yaml')
        vnfd = join(build_dir, 'vnfd', 'sdk_descriptor.yaml')
        os.makedirs(dirname(vnfd), exist_ok=True)
        shutil.copy(t_vnfd, vnfd)

        _uuid = uuid.uuid1()
        _now = datetime.datetime.now().strftime('%FT%TZ')

        changes = [
            ('<<PRODUCT>>', csar_name),
            ('<<VERSION>>', csar_version),
            ('<<DATE>>', _now),
            ('<<DESCRIPTOR_ID>>', str(_uuid)),
            ('<<PRODUCT_SET>>', product_set),
            ('<<CHART>>', _chart_filename)
        ]

        for _file in [manifest, vnfd]:
            for _change in changes:
                self.info('SdkBuildManager',
                          'Updating {0} with {1}'.format(_file, _change[1]))
                Base().replace_value(_file, _change[1], _change[0])

        return build_dir, vnfd, manifest

    def generate_csar(self, csar_name: str, build_dir: str, vndf: str,
                      manifest: str, am_package_manager: str,
                      light: bool):
        docker_sock = '/var/run/docker.sock:/var/run/docker.sock'
        command = [
            'docker', 'run', '--rm',
            '-v', '{0}:{0}'.format(build_dir),
            '-v', docker_sock,
            '-w', build_dir,
            am_package_manager,
            'generate',
            '--helm3',
            '--helm-dir', join(build_dir, 'charts'),
            '--name', csar_name,
            '--manifest', manifest,
            '--vnfd', vndf,
            '--set', 'images.eric-enm-monitoring.enabled=false']
        if light:
            command.append('--no-images')

        self.info('SdkBuildManager',
                  'Creating CSAR from {0} '.format(build_dir))
        print(' '.join(command))
        self._execute(command)

        sdk_csar = join(build_dir, '{0}.csar'.format(csar_name))
        if not exists(sdk_csar):
            raise FileNotFoundError('{0} not found!'.format(sdk_csar))
        self._execute(['unzip', '-l', sdk_csar])

    def rebuild_csar(self, chart_yaml: str, output_dir: str,
                     template: str, product_set: str, am_package_manager: str,
                     light: bool) -> None:
        integ_chart, _name, _version = self.integration_chart(
            chart_yaml, template, output_dir)

        build_dir, vndf, manifest = self.prepare_csar(
            _name, _version, integ_chart, product_set, output_dir)

        self.generate_csar(
            '{0}-{1}'.format(_name, _version), build_dir, vndf, manifest,
            am_package_manager, light)

    @staticmethod
    def get_retagged_image(image, repository):
        current_tag_parts = image.split('/', 1)
        current_tag_host = current_tag_parts[0]
        current_tag_path = current_tag_parts[1]

        current_tag_image = current_tag_path.split('/')[-1]
        current_tag_path = '/'.join(current_tag_path.split('/')[:-1])

        repository_parts = repository.split('/', 1)
        repository_tag_host = repository_parts[0]
        if len(repository_parts) > 1:
            repository_tag_path = repository_parts[1]
        else:
            repository_tag_path = current_tag_path

        if current_tag_host != repository_tag_host or \
                current_tag_path != repository_tag_path:
            new_tag = '{0}/{1}/{2}'.format(
                repository_tag_host,
                repository_tag_path,
                current_tag_image)
            return new_tag
        else:
            return image

    def load_csar_images(self, repository: str, images_txt: str) -> None:
        if not exists(images_txt):
            raise SystemExit('File {0} not found'.format(images_txt))
        docker_tar = abspath(join(dirname(images_txt), 'docker.tar'))
        self.info('SdkBuildManager',
                  'Load images from {0} and re-tag to {1}'.format(
                      docker_tar, repository))

        docker = Docker()
        docker.load_images(docker_tar)
        retagged = []
        already = []
        with open(images_txt) as _reader:
            for image in _reader.readlines():
                image = image.strip()
                new_tag = self.get_retagged_image(image, repository)

                if new_tag != image:
                    retagged.append(new_tag)
                    if docker.exists(new_tag):
                        already.append(new_tag)
                        self.info(
                            'SdkBuildManager',
                            'Image already re-tagged: {0}'.format(new_tag))
                    else:
                        docker.retag(image, new_tag)
                else:
                    self.info('SdkBuildManager',
                              'No need to re-tag {0}'.format(image))
                if docker.exists(image):
                    docker.remove([image])
        docker.push_images(retagged)

    def load_am_package_manager(self, images_txt: str, repository: str):
        am_package_manager = ''
        with open(images_txt) as _reader:
            for image in _reader.readlines():
                image = image.strip()
                if "eric-am-package-manager" in image:
                    return self.get_retagged_image(image, repository)
        return am_package_manager

    def get_am_package_manager_image(self, repository_url: str,
                                     sdk_images: str) -> str:
        if not exists(sdk_images):
            raise SystemExit('File {0} not found'.format(sdk_images))

        _am_pkg_mgr_manager = self.load_am_package_manager(
            sdk_images, repository_url)

        if not _am_pkg_mgr_manager:
            raise SystemExit('am-package-manager image is not found')
        return _am_pkg_mgr_manager


def parse_args():
    parser = argparse.ArgumentParser(description='something ...')
    parser.add_argument('--verbose', help='verbose help', action='store_true')

    # --repository-url : If only a hostname is set, image tags will be updated
    # to use that host and the repository path will not change
    #   --repository-url=host-b
    #       host-a/path/image:latest -> host-b/path/image:latest
    # If both a host and repository path are set, both will be used
    #   --repository-url=host-b/internal
    #       host-a/path/image:latest -> host-b/internal/image:latest
    parser.add_argument(
        '--repository-url', help='URL of a docker registry')
    parser.add_argument('-d', dest='overwrite', action='store_true',
                        help='delete')

    parser.add_argument('--load-csar-images', help='load-csar-images help',
                        action='store_true')

    sdk_images = abspath(
        join(basename(__file__), '..', '..', 'docker', 'images.txt'))

    parser.add_argument('-i', help='Path to SDK images.txt', dest='sdk_images',
                        default=sdk_images)

    parser.add_argument('--build-load-images', help='build-load-images help',
                        action='store_true')
    parser.add_argument('--sdk-path', help='SDK Chart template')

    integ_template = abspath(
        join(basename(__file__), '..', '..', 'templates',
             'charts', 'eric-enm-sdk-integration-template-0.0.0.tgz'))
    parser.add_argument('--integ-sdk-path', default=integ_template,
                        help='SDK Integration Chart template')

    parser.add_argument('--sdk-input-path', help='sdk-input-path help')

    parser.add_argument('--update-config', help='update-config help',
                        action='store_true')
    parser.add_argument('--custom-sdk-path', help='custom-sdk-path help')

    def _file_path(arg_parser, arg_name, file_path):
        if not exists(file_path):
            arg_parser.error('{0}: {1} not found!'.format(arg_name, file_path))
        else:
            return file_path

    parser.add_argument(
        '--rebuild-csar',
        help='Build a CSAR that can be used to install '
             'one or more SDK charts.'
             'Value points to Chart.yaml ',
        dest='rebuild_csar',
        type=lambda arg: _file_path(parser, '--rebuild-csar', arg))

    parser.add_argument(
        '--product-set', dest='product_set',
        help='ENM ProductSet the SDK Integration CSAR is targeting')

    parser.add_argument('--csar-name-version', help='csar-name-version help')
    parser.add_argument('--csar-light', help='Build a light version of '
                                             'the SDK CSAR',
                        action='store_true', default=False)

    if len(sys.argv) <= 1:
        parser.print_help()
        exit(2)
    __args = parser.parse_args()

    def check_option(option, opt_arg, required, req_arg):
        if option and not required:
            parser.print_usage(file=sys.stderr)
            print('{0}: error: argument --{1}: expected one argument '
                  '--{2}'.format(sys.argv[0], opt_arg, req_arg),
                  file=sys.stderr)
            exit(2)

    check_option(__args.load_csar_images, 'load-csar-images',
                 __args.repository_url, 'repository-url')

    check_option(__args.build_load_images, 'build-load-images',
                 __args.sdk_path, 'sdk-path')
    check_option(__args.build_load_images, 'build-load-images',
                 __args.sdk_input_path, 'sdk-input-path')

    check_option(__args.update_config, 'update-config',
                 __args.repository_url, 'repository-url')

    check_option(__args.rebuild_csar, 'rebuild-csar',
                 __args.custom_sdk_path, 'custom-sdk-path')

    check_option(__args.rebuild_csar, 'rebuild-csar',
                 __args.product_set, 'product_set')

    check_option(__args.rebuild_csar, 'rebuild-csar',
                 __args.repository_url, 'repository-url')

    if __args.update_config:
        if not __args.custom_sdk_path and not __args.build_load_images:
            parser.print_usage(file=sys.stderr)
            print('{0}: error: argument --update-config: expected one '
                  'argument --custom-sdk-path'.format(sys.argv[0]),
                  file=sys.stderr)

    return __args


if __name__ == '__main__':
    binaries = ['docker', 'helm']
    _b = False
    for binary in binaries:
        if not Base.which(binary):
            _b = True
            print('Binary "{0}" not in $PATH'.format(binary), file=sys.stderr)

    if _b:
        exit(3)

    _main_opts = parse_args()
    VERBOSE = _main_opts.verbose

    build_mgr = SdkBuildManager()
    if _main_opts.load_csar_images:
        build_mgr.load_csar_images(_main_opts.repository_url,
                                   _main_opts.sdk_images)
    if _main_opts.build_load_images:
        build_mgr.generate_chart(
            _main_opts.sdk_path, _main_opts.sdk_input_path,
            _main_opts.repository_url, _main_opts.custom_sdk_path,
            _main_opts.overwrite)
    if _main_opts.rebuild_csar:
        _am_package_manager = build_mgr.get_am_package_manager_image(
            _main_opts.repository_url, _main_opts.sdk_images
        )
        build_mgr.rebuild_csar(_main_opts.rebuild_csar,
                               _main_opts.custom_sdk_path,
                               _main_opts.integ_sdk_path,
                               _main_opts.product_set,
                               _am_package_manager,
                               _main_opts.csar_light)
