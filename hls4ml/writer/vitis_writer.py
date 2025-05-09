import glob
import os
from pathlib import Path
from shutil import copy
from distutils.dir_util import copy_tree
from shutil import copyfile, copytree, rmtree

from hls4ml.writer.vivado_writer import VivadoWriter
from hls4ml.writer.vivado_accelerator_writer import VivadoAcceleratorWriter


class VitisWriter(VivadoAcceleratorWriter):
    def __init__(self):
        super().__init__()
        self.vivado_accelerator_config = None

    def write_nnet_utils_overrides(self, model):
        ###################
        # nnet_utils
        ###################
        
        filedir = os.path.dirname(os.path.abspath(__file__))

        srcpath = os.path.join(filedir, '../templates/vitis/nnet_utils/')
        dstpath = f'{model.config.get_output_dir()}/firmware/nnet_utils/'

        headers = [os.path.basename(h) for h in glob.glob(srcpath + '*.h')]

        for h in headers:
            copy(srcpath + h, dstpath + h)
        

    def write_board_script_override(self, model):
        '''
        Write the tcl scripts and kernel sources to create a Vitis IPI
        '''
        '''
        ###################
        # project.tcl
        ###################

        prj_tcl_file = Path(f'{model.config.get_output_dir()}/project.tcl')
        with open(prj_tcl_file) as f:
            prj_tcl_contents = f.readlines()
            for line_num, line in enumerate(prj_tcl_contents):
                if 'set backend' in line:
                    prj_tcl_contents[line_num] = 'set backend "vitis"\n'
                if 'set clock_uncertainty' in line:
                    prj_tcl_contents[line_num] = 'set clock_uncertainty {}\n'.format(
                        model.config.get_config_value('ClockUncertainty', '27%')
                    )

        with open(prj_tcl_file, 'w') as f:
            f.writelines(prj_tcl_contents)
        '''

        '''
        Write the tcl scripts and kernel sources to create a Vivado IPI project for the VivadoAccelerator
        '''
        filedir = os.path.dirname(os.path.abspath(__file__))
        copyfile(
            os.path.join(filedir, self.vivado_accelerator_config.get_tcl_file_path()),
            f'{model.config.get_output_dir()}/design.tcl',
        )
        # Generic alveo board
        if self.vivado_accelerator_config.get_board().startswith('alveo'):
            src_dir = os.path.join(filedir, self.vivado_accelerator_config.get_krnl_rtl_src_dir())
            dst_dir = os.path.abspath(model.config.get_output_dir()) + '/src'
            copy_tree(src_dir, dst_dir)

        ###################
        # project.tcl
        ###################
        f = open(f'{model.config.get_output_dir()}/project.tcl', 'w')
        f.write('variable project_name\n')
        f.write(f'set project_name "{model.config.get_project_name()}"\n')
        f.write('variable backend\n')
        f.write('set backend "vitis"\n')
        f.write('variable part\n')
        f.write(f'set part "{self.vivado_accelerator_config.get_part()}"\n')
        f.write('variable clock_period\n')
        f.write('set clock_period {}\n'.format(model.config.get_config_value('ClockPeriod')))
        f.write('variable clock_uncertainty\n')
        f.write('set clock_uncertainty {}\n'.format(model.config.get_config_value('ClockUncertainty', '27%')))
        f.write('variable version\n')
        f.write('set version "{}"\n'.format(model.config.get_config_value('Version', '1.0.0')))
        f.write('variable maximum_size\n')
        f.write('set maximum_size {}\n'.format(model.config.get_config_value('MaximumSize', '4096')))
        if self.vivado_accelerator_config.get_interface() == 'axi_stream':
            in_bit, out_bit = self.vivado_accelerator_config.get_io_bitwidth()
            f.write(f'set bit_width_hls_output {in_bit}\n')
            f.write(f'set bit_width_hls_input {out_bit}\n')
        f.close()

    def write_hls(self, model):
        """
        Write the HLS project. Calls the steps from VivadoWriter, adapted for Vitis
        
        from hls4ml.backends import VivadoAcceleratorConfig

        self.vivado_accelerator_config = VivadoAcceleratorConfig(
            model.config, model.get_input_variables(), model.get_output_variables()
        )
        super().write_hls(model)
        self.write_nnet_utils_overrides(model)
        self.write_board_script_override(model)
        self.write_tar(model)
        """
        
        VivadoAcceleratorWriter.write_hls(self, model)
