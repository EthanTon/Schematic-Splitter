            output_location = (
                output_directory + "/" + output_name + str(file_num) + ".schem"
            )

            if not os.path.isdir(output_directory):
                os.mkdir(output_directory)

            output.save(output_location)