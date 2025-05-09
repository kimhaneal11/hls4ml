import os
import sys

from hls4ml.backends import VivadoBackend
from hls4ml.model.flow import get_flow, register_flow
from hls4ml.report import parse_vivado_report


class VitisBackend(VivadoBackend):
    def __init__(self):
        super(VivadoBackend, self).__init__(name='Vitis')
        self._register_layer_attributes()
        self._register_flows()

    def _register_flows(self):
        validation_passes = [
            'vitis:validate_conv_implementation',
            'vitis:validate_resource_strategy',
            'vitis:validate_resource_unrolled_strategy',
        ]
        validation_flow = register_flow('validation', validation_passes, requires=['vivado:init_layers'], backend=self.name)

        # Any potential templates registered specifically for Vitis backend
        template_flow = register_flow(
            'apply_templates', self._get_layer_templates, requires=['vivado:init_layers'], backend=self.name
        )

        writer_passes = ['make_stamp', 'vitis:write_hls']
        self._writer_flow = register_flow('write', writer_passes, requires=['vitis:ip'], backend=self.name)

        ip_flow_requirements = get_flow('vivado:ip').requires.copy()
        ip_flow_requirements.insert(ip_flow_requirements.index('vivado:init_layers'), validation_flow)
        ip_flow_requirements.insert(ip_flow_requirements.index('vivado:apply_templates'), template_flow)

        self._default_flow = register_flow('ip', None, requires=ip_flow_requirements, backend=self.name)

        # Register the fifo depth optimization flow which is different from the one for vivado
        fifo_depth_opt_passes = [
            'vitis:fifo_depth_optimization'
        ] + writer_passes  # After optimization, a new project will be written

        register_flow('fifo_depth_optimization', fifo_depth_opt_passes, requires=['vitis:ip'], backend=self.name)

    def create_initial_config(
        self,
        board='pynq-z2',
        part='xcvu13p-flga2577-2-e',
        clock_period=5,
        clock_uncertainty='27%',
        io_type='io_parallel',
        interface='axi_stream',
        driver='python',
        input_type='float',
        output_type='float',
        platform='xilinx_u250_xdma_201830_2',
        **_,
    ):
        """Create initial configuration of the Vitis backend.

        Args:
            part (str, optional): The FPGA part to be used. Defaults to 'xcvu13p-flga2577-2-e'.
            clock_period (int, optional): The clock period. Defaults to 5.
            clock_uncertainty (str, optional): The clock uncertainty. Defaults to 27%.
            io_type (str, optional): Type of implementation used. One of
                'io_parallel' or 'io_stream'. Defaults to 'io_parallel'.
            namespace (str, optional): If defined, place all generated code within a namespace. Defaults to None.
            write_weights_txt (bool, optional): If True, writes weights to .txt files which speeds up compilation.
                Defaults to True.
            write_tar (bool, optional): If True, compresses the output directory into a .tar.gz file. Defaults to False.

        Returns:
            dict: initial configuration.
        """
        config = super().create_initial_config(part, clock_period, clock_uncertainty, io_type)
        config['AcceleratorConfig'] = {}
        config['AcceleratorConfig']['Board'] = board
        config['AcceleratorConfig']['Interface'] = interface  # axi_stream, axi_master, axi_lite
        config['AcceleratorConfig']['Driver'] = driver
        config['AcceleratorConfig']['Precision'] = {}
        config['AcceleratorConfig']['Precision']['Input'] = {}
        config['AcceleratorConfig']['Precision']['Output'] = {}
        config['AcceleratorConfig']['Precision']['Input'] = input_type  # float, double or ap_fixed<a,b>
        config['AcceleratorConfig']['Precision']['Output'] = output_type  # float, double or ap_fixed<a,b>
        if board.startswith('alveo'):
            config['AcceleratorConfig']['Platform'] = platform

        return config

    def build(
        self,
        model,
        reset=False,
        csim=True,
        synth=True,
        cosim=False,
        validation=False,
        export=False,
        vsynth=False,
        fifo_opt=False,
        bitfile=False,
    ):
        if 'linux' in sys.platform:
            found = os.system('command -v vitis_hls > /dev/null')
            if found != 0:
                raise Exception('Vitis HLS installation not found. Make sure "vitis_hls" is on PATH.')

        curr_dir = os.getcwd()
        os.chdir(model.config.get_output_dir())
        os.system(
            (
                'vitis_hls -f build_prj.tcl "reset={reset} csim={csim} synth={synth} cosim={cosim} '
                'validation={validation} export={export} vsynth={vsynth} fifo_opt={fifo_opt}"'
            ).format(
                reset=reset,
                csim=csim,
                synth=synth,
                cosim=cosim,
                validation=validation,
                export=export,
                vsynth=vsynth,
                fifo_opt=fifo_opt,
            )
        )
        os.chdir(curr_dir)

        # Get Config to view Board and Platform
        from hls4ml.backends import VivadoAcceleratorConfig

        vivado_accelerator_config = VivadoAcceleratorConfig(
            model.config, model.get_input_variables(), model.get_output_variables()
        )

        # now make a bitfile
        if bitfile:
            if vivado_accelerator_config.get_board().startswith('alveo'):
                self.make_xclbin(model, vivado_accelerator_config.get_platform())
            else:
                curr_dir = os.getcwd()
                os.chdir(model.config.get_output_dir())
                try:
                    os.system('vivado -mode batch -source design.tcl')
                except Exception:
                    print("Something went wrong, check the Vivado logs")
                os.chdir(curr_dir)


        return parse_vivado_report(model.config.get_output_dir())
    
    def make_xclbin(self, model, platform='xilinx_u250_xdma_201830_2'):
        """Create the xclbin for the given model and target platform.

        Args:
            model (ModelGraph): Compiled and build model.
            platform (str, optional): Development/Deployment target platform, must be installed first.
                The host machine only requires the deployment target platform. Refer to the Getting Started section of
                the Alveo guide. Defaults to 'xilinx_u250_xdma_201830_2'.
        """
        curr_dir = os.getcwd()
        abs_path_dir = os.path.abspath(model.config.get_output_dir())
        os.chdir(abs_path_dir)
        print(abs_path_dir)
        os.makedirs('xo_files', exist_ok=True)
        try:
            os.system('vivado -mode batch -source design.tcl')
        except Exception:
            print("Something went wrong, check the Vivado logs")
        project_name = model.config.get_project_name()
        ip_repo_path = abs_path_dir + '/' + project_name + '_prj' + '/solution1/impl/ip'
        os.makedirs('xclbin_files', exist_ok=True)
        os.chdir(abs_path_dir + '/xclbin_files')
        # TODO Add other platforms
        vitis_cmd = (
            "v++ -t hw --platform "
            + platform
            + " --link ../xo_files/"
            + project_name
            + "_kernel.xo -o'"
            + project_name
            + "_kernel.xclbin' --user_ip_repo_paths "
            + ip_repo_path
        )
        try:
            os.system(vitis_cmd)
        except Exception:
            print("Something went wrong, check the Vitis/Vivado logs")
        os.chdir(curr_dir)
